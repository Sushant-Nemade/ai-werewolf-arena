"""Ollama provider — the default for real local inference."""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMResponse, Stopwatch, estimate_tokens


class OllamaProvider:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"ollama/{model}"
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 400,
        temperature: float = 0.7,
    ) -> LLMResponse:
        sw = Stopwatch()
        resp = await self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            model=self.model,
            latency_ms=sw.elapsed_ms(),
            prompt_tokens=int(data.get("prompt_eval_count") or estimate_tokens("".join(m.content for m in messages))),
            completion_tokens=int(data.get("eval_count") or estimate_tokens(text)),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


_: type[LLMProvider] = OllamaProvider
