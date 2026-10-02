"""OpenAI-compatible provider (OpenAI, Azure OpenAI, vLLM, LiteLLM gateways)."""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMResponse, Stopwatch, estimate_tokens


class OpenAIProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        if not api_key:
            raise ValueError("openai provider requires ARENA_OPENAI_API_KEY")
        self.model = model
        self.name = f"openai/{model}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 400,
        temperature: float = 0.7,
    ) -> LLMResponse:
        sw = Stopwatch()
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=self.model,
            latency_ms=sw.elapsed_ms(),
            prompt_tokens=int(usage.get("prompt_tokens") or estimate_tokens("".join(m.content for m in messages))),
            completion_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


_: type[LLMProvider] = OpenAIProvider
