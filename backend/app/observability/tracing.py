"""Decision tracing.

Every agent decision is recorded with enough context to audit it later: which
prompt went in (hashed — full prompts can be large), which memories were
retrieved, what the model emitted, how the guardrail layer handled it, and how
long it took. Traces power the in-game "decision inspector" and the evaluation
harness.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class DecisionTrace:
    id: str
    game_id: str
    round: int
    phase: str
    agent: str
    task: str
    model: str
    prompt_hash: str
    prompt_chars: int
    retrieved_memory_ids: list[str]
    raw_output: str
    parsed_output: dict | None
    guardrail_attempts: int
    fail_closed: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def hash_prompt(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class DecisionTracer:
    def __init__(self) -> None:
        self._traces: dict[str, list[DecisionTrace]] = {}

    def new_trace(self, **kwargs) -> DecisionTrace:
        return DecisionTrace(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )

    def record(self, trace: DecisionTrace) -> None:
        self._traces.setdefault(trace.game_id, []).append(trace)

    def for_game(self, game_id: str) -> list[DecisionTrace]:
        return list(self._traces.get(game_id, []))

    def summary(self, game_id: str) -> dict:
        traces = self.for_game(game_id)
        if not traces:
            return {"decisions": 0, "fail_closed": 0, "avg_latency_ms": 0.0}
        return {
            "decisions": len(traces),
            "fail_closed": sum(1 for t in traces if t.fail_closed),
            "avg_latency_ms": round(sum(t.latency_ms for t in traces) / len(traces), 1),
            "total_prompt_tokens": sum(t.prompt_tokens for t in traces),
            "total_completion_tokens": sum(t.completion_tokens for t in traces),
        }
