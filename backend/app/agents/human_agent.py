"""Human seat.

A human player participates through the API/frontend. The engine awaits their
action on an asyncio queue; if the timeout expires, the seat fails safe (pass /
abstain / first legal candidate) so one idle player cannot stall the arena.
Stale submissions are drained before waiting so queued input cannot leak across
phases.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, ValidationError

from ..game.models import NightAction, Player, PlayerView, SpeechAction, VoteAction


class HumanAgent:
    def __init__(self, player: Player, timeout_seconds: int = 600) -> None:
        self.player = player
        self.timeout_seconds = timeout_seconds
        self._queue: asyncio.Queue[BaseModel] = asyncio.Queue()

    async def submit(self, action: BaseModel) -> None:
        await self._queue.put(action)

    def _drain(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def _wait(self, schema: type[SpeechAction] | type[VoteAction] | type[NightAction]):
        self._drain()
        try:
            raw = await asyncio.wait_for(self._queue.get(), timeout=self.timeout_seconds)
            return schema.model_validate(raw)
        except (asyncio.TimeoutError, ValidationError):
            return None

    async def speak(self, view: PlayerView, candidates: list[str]) -> SpeechAction:
        action = await self._wait(SpeechAction)
        return action or SpeechAction(statement="(says nothing)", suspicion=None)

    async def vote(self, view: PlayerView, candidates: list[str]) -> VoteAction:
        action = await self._wait(VoteAction)
        return action or VoteAction(target="abstain", reason="timed out")

    async def night_action(self, view: PlayerView, kind: str, candidates: list[str]) -> NightAction:
        action = await self._wait(NightAction)
        return action or NightAction(kind=kind, target=candidates[0])
