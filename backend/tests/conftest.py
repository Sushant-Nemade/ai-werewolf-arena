"""Shared helpers for the test suite."""

from __future__ import annotations

from app.config import Settings


def make_settings(**overrides) -> Settings:
    base = {
        "llm_provider": "mock",
        "guardrail_max_retries": 2,
        "memory_top_k": 5,
        "max_rounds": 20,
    }
    base.update(overrides)
    return Settings(**base)
