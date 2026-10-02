"""Output safety guardrails.

Agents' utterances are shown to human players, so generated text passes through
a lightweight safety layer before it becomes part of the public game record:
length is bounded and a small blocklist is redacted. The blocklist is
deliberately tiny and easy to extend; it is a screening signal, not a complete
moderation system (documented in the README trade-offs).
"""

from __future__ import annotations

MAX_STATEMENT_CHARS = 600

_BLOCKLIST = {
    "kill yourself",
    "kys",
}


def sanitize_statement(text: str, max_chars: int = MAX_STATEMENT_CHARS) -> tuple[str, list[str]]:
    """Return (safe_text, flags). Flags record what the guardrail changed."""
    flags: list[str] = []
    safe = " ".join(text.split())  # normalise whitespace

    lowered = safe.lower()
    for term in _BLOCKLIST:
        if term in lowered:
            safe = re_sub_case_insensitive(term, safe)
            flags.append(f"redacted:{term}")

    if len(safe) > max_chars:
        safe = safe[: max_chars - 1].rstrip() + "…"
        flags.append("truncated")

    return safe, flags


def re_sub_case_insensitive(term: str, text: str) -> str:
    import re

    return re.sub(re.escape(term), "[redacted]", text, flags=re.IGNORECASE)
