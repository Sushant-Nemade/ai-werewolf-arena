"""Provider factory."""

from __future__ import annotations

from ..config import Settings
from .base import LLMProvider
from .mock import DeterministicMockLLM
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider


def create_provider(settings: Settings, override: str | None = None, seed: int | None = None) -> LLMProvider:
    name = (override or settings.llm_provider or "mock").lower()
    if name == "mock":
        return DeterministicMockLLM(seed=seed or 0)
    if name == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    if name == "openai":
        return OpenAIProvider(settings.openai_base_url, settings.openai_api_key, settings.openai_model)
    raise ValueError(f"unknown LLM provider: {name!r} (expected mock | ollama | openai)")
