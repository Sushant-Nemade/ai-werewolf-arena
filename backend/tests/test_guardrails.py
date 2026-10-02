import asyncio

from app.guardrails.safety import sanitize_statement
from app.guardrails.structured import extract_json, generate_structured
from app.llm.base import ChatMessage, LLMResponse
from app.game.models import VoteAction


class StubProvider:
    """Returns a fixed sequence of outputs, then repeats the last one."""

    name = "stub"

    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, messages, *, max_tokens=400, temperature=0.0) -> LLMResponse:
        text = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return LLMResponse(text=text, model="stub", latency_ms=1.0)


MESSAGES = [ChatMessage("user", "TASK: vote\nCANDIDATES: p1,p2")]


def run(coro):
    return asyncio.run(coro)


def test_extract_json_from_prose():
    assert extract_json('Sure! Here you go:\n```json\n{"kind": "vote", "target": "p2"}\n```') == {
        "kind": "vote",
        "target": "p2",
    }


def test_valid_output_first_attempt():
    provider = StubProvider(['{"kind": "vote", "target": "p1", "reason": "x"}'])
    value, report, _ = run(generate_structured(provider, MESSAGES, VoteAction, max_retries=2))
    assert value is not None and value.target == "p1"
    assert report.attempts == 1 and report.succeeded and not report.fail_closed


def test_retry_after_garbage_then_success():
    provider = StubProvider(["not json at all", '{"kind": "vote", "target": "p2"}'])
    value, report, _ = run(generate_structured(provider, MESSAGES, VoteAction, max_retries=2))
    assert value is not None and value.target == "p2"
    assert report.attempts == 2 and len(report.errors) == 1
    assert provider.calls == 2


def test_fail_closed_after_exhausted_retries():
    provider = StubProvider(["garbage"])
    value, report, _ = run(generate_structured(provider, MESSAGES, VoteAction, max_retries=2))
    assert value is None
    assert report.fail_closed and report.attempts == 3 and not report.succeeded


def test_domain_validator_rejects_illegal_target():
    provider = StubProvider(['{"kind": "vote", "target": "p99"}', '{"kind": "vote", "target": "p1"}'])

    def validator(v: VoteAction) -> None:
        if v.target not in {"p1", "p2"}:
            raise ValueError("target is not a living candidate")

    value, report, _ = run(
        generate_structured(provider, MESSAGES, VoteAction, max_retries=2, validator=validator)
    )
    assert value is not None and value.target == "p1"
    assert report.attempts == 2


def test_safety_truncates_and_redacts():
    long_text = "word " * 300
    safe, flags = sanitize_statement(long_text)
    assert len(safe) <= 600
    assert "truncated" in flags

    safe, flags = sanitize_statement("You should go kill yourself, wolf.")
    assert "[redacted]" in safe and "kill yourself" not in safe.lower()
    assert any(f.startswith("redacted") for f in flags)
