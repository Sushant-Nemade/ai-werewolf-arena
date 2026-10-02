"""Structured-output guardrails.

LLMs are unreliable JSON printers. This layer wraps every model call with:

1. JSON extraction tolerant of surrounding prose / markdown fences,
2. Pydantic schema validation plus an optional domain validator
   (e.g. "target must be a living candidate"),
3. bounded retries that feed the validation error back to the model,
4. a fail-closed result when retries are exhausted — the caller falls back to a
   safe default action instead of executing unvalidated output.

Every attempt is returned so the tracer can record the full retry trajectory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from pydantic import BaseModel

from ..llm.base import ChatMessage, LLMProvider, LLMResponse

T = TypeVar("T", bound=BaseModel)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class GuardrailReport:
    attempts: int
    succeeded: bool
    fail_closed: bool
    errors: list[str] = field(default_factory=list)


def extract_json(text: str) -> dict:
    """Extract the first JSON object from raw model text."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE)
    match = _JSON_RE.search(cleaned)
    if not match:
        raise ValueError("no JSON object found in model output")
    return json.loads(match.group(0))


async def generate_structured(
    provider: LLMProvider,
    messages: list[ChatMessage],
    schema: type[T],
    *,
    max_retries: int = 2,
    validator: Callable[[T], None] | None = None,
    max_tokens: int = 400,
    temperature: float = 0.7,
) -> tuple[T | None, GuardrailReport, list[LLMResponse]]:
    """Call the provider until ``schema`` validates or retries run out."""
    errors: list[str] = []
    responses: list[LLMResponse] = []
    conversation = list(messages)
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        response = await provider.complete(conversation, max_tokens=max_tokens, temperature=temperature)
        responses.append(response)
        try:
            value = schema.model_validate(extract_json(response.text))
            if validator is not None:
                validator(value)
            return value, GuardrailReport(attempt, True, False, errors), responses
        except Exception as exc:  # validation / extraction / domain errors
            errors.append(f"attempt {attempt}: {exc}")
            conversation.append(ChatMessage("assistant", response.text))
            conversation.append(
                ChatMessage(
                    "user",
                    "Your previous output was invalid: "
                    f"{exc}. Respond with ONLY the corrected JSON object, no prose.",
                )
            )

    return None, GuardrailReport(total_attempts, False, True, errors), responses
