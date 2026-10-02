"""LLM-backed agent.

The decision loop is deliberately uniform across tasks:

    perceive (PlayerView) -> remember (episodic retrieval) -> reason (LLM)
    -> validate (structured + safety guardrails) -> act -> trace

Fail-closed behaviour: if the model never produces a valid action, the agent
falls back to a safe default (pass the speech, abstain the vote, first legal
candidate at night) and the failure is recorded in the trace and metrics.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from pydantic import BaseModel

from ..config import Settings
from ..game.models import NightAction, Player, PlayerView, SpeechAction, VoteAction
from ..game.prompts import system_prompt, task_prompt
from ..guardrails.safety import sanitize_statement
from ..guardrails.structured import generate_structured
from ..llm.base import ChatMessage, LLMProvider
from ..memory.store import EpisodicMemory
from ..observability.metrics import metrics
from ..observability.tracing import DecisionTracer, hash_prompt

T = TypeVar("T", bound=BaseModel)


class LLMAgent:
    def __init__(
        self,
        player: Player,
        provider: LLMProvider,
        memory: EpisodicMemory,
        tracer: DecisionTracer,
        settings: Settings,
        game_id: str,
    ) -> None:
        self.player = player
        self.provider = provider
        self.memory = memory
        self.tracer = tracer
        self.settings = settings
        self.game_id = game_id

    # ------------------------------------------------------------------ tasks

    async def speak(self, view: PlayerView, candidates: list[str]) -> SpeechAction:
        def valid(a: SpeechAction) -> None:
            if a.suspicion is not None and a.suspicion not in candidates:
                raise ValueError(f"suspicion {a.suspicion!r} is not a living candidate")
            if not a.statement.strip():
                raise ValueError("statement must not be empty")

        action = await self._act(
            "speak", view, candidates, SpeechAction, valid,
            fallback=SpeechAction(statement="I need a moment to think. I pass.", suspicion=None),
        )
        safe, flags = sanitize_statement(action.statement)
        if flags:
            metrics.inc("guardrails.safety_flags")
        action.statement = safe
        return action

    async def vote(self, view: PlayerView, candidates: list[str]) -> VoteAction:
        def valid(a: VoteAction) -> None:
            if a.target not in candidates:
                raise ValueError(f"vote target {a.target!r} is not a living candidate")

        return await self._act(
            "vote", view, candidates, VoteAction, valid,
            fallback=VoteAction(target="abstain", reason="guardrail fallback: no valid vote produced"),
        )

    async def night_action(self, view: PlayerView, kind: str, candidates: list[str]) -> NightAction:
        task = f"night_{kind}"

        def valid(a: NightAction) -> None:
            if a.target not in candidates:
                raise ValueError(f"night target {a.target!r} is not a legal candidate")

        fallback = NightAction(kind=kind, target=candidates[0])
        return await self._act(task, view, candidates, NightAction, valid, fallback=fallback)

    # ------------------------------------------------------------ generic act

    async def _act(
        self,
        task: str,
        view: PlayerView,
        candidates: list[str],
        schema: type[T],
        validator: Callable[[T], None],
        fallback: T,
    ) -> T:
        query = " ".join(e.content for e in view.recent_events[-4:]) + " suspicion votes werewolf"
        retrieved = self.memory.retrieve(query, k=self.settings.memory_top_k)
        memory_texts = [r.item.text for r in retrieved]

        user_prompt = task_prompt(task, view, candidates, memory_texts)
        messages = [
            ChatMessage("system", system_prompt(self.player)),
            ChatMessage("user", user_prompt),
        ]

        value, report, responses = await generate_structured(
            self.provider,
            messages,
            schema,
            max_retries=self.settings.guardrail_max_retries,
            validator=validator,
            max_tokens=self.settings.max_output_tokens,
            temperature=self.settings.temperature,
        )

        latency = sum(r.latency_ms for r in responses)
        trace = self.tracer.new_trace(
            game_id=self.game_id,
            round=view.round,
            phase=view.phase.value,
            agent=self.player.id,
            task=task,
            model=responses[-1].model if responses else self.provider.name,
            prompt_hash=hash_prompt(user_prompt),
            prompt_chars=len(user_prompt),
            retrieved_memory_ids=[r.item.id for r in retrieved],
            raw_output=responses[-1].text if responses else "",
            parsed_output=value.model_dump() if value else None,
            guardrail_attempts=report.attempts,
            fail_closed=report.fail_closed,
            latency_ms=round(latency, 1),
            prompt_tokens=sum(r.prompt_tokens for r in responses),
            completion_tokens=sum(r.completion_tokens for r in responses),
        )
        self.tracer.record(trace)
        metrics.inc("decisions.total")
        metrics.observe_latency("decisions.latency", latency)
        if report.fail_closed:
            metrics.inc("decisions.fail_closed")

        return value if value is not None else fallback
