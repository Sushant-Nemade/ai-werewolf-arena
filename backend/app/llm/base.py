"""Provider-agnostic LLM interface.

Every provider returns the same ``LLMResponse`` envelope so the guardrail,
tracing and evaluation layers never branch on vendor specifics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 400,
        temperature: float = 0.7,
    ) -> LLMResponse: ...


def estimate_tokens(text: str) -> int:
    """Rough token estimate used when a provider does not report usage."""
    return max(1, len(text) // 4)


class Stopwatch:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
