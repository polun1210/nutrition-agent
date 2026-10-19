"""模型閘道：VLM、LLM、embedding 共用的單一介面，正式實作走 OpenRouter。"""

import base64
from typing import Protocol

import httpx

from nutrition_agent.config import Settings


class ModelGateway(Protocol):
    def vision(self, prompt: str, image: bytes, mime_type: str) -> str: ...

    def complete(self, prompt: str, system: str | None = None) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenRouterGateway:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        vlm_model: str,
        llm_model: str,
        embedding_model: str,
        provider: str = "",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._vlm_model = vlm_model
        self._llm_model = llm_model
        self._embedding_model = embedding_model
        self._provider = provider
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=timeout,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenRouterGateway":
        return cls(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            vlm_model=settings.vlm_model,
            llm_model=settings.llm_model,
            embedding_model=settings.embedding_model,
            provider=settings.openrouter_provider,
        )

    def vision(self, prompt: str, image: bytes, mime_type: str) -> str:
        data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode()}"
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        return self._chat(self._vlm_model, [{"role": "user", "content": content}])

    def complete(self, prompt: str, system: str | None = None) -> str:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        return self._chat(self._llm_model, messages)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post(
            "/embeddings", json={"model": self._embedding_model, "input": texts}
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]

    def _chat(self, model: str, messages: list[dict]) -> str:
        body: dict = {"model": model, "messages": messages}
        if self._provider:
            body["provider"] = {"order": [self._provider], "allow_fallbacks": False}
        response = self._client.post("/chat/completions", json=body)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
