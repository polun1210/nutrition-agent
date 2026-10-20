"""模型閘道：VLM、LLM、embedding 共用的單一介面，正式實作走 OpenRouter。"""

import base64
import time
from collections.abc import Callable
from typing import Protocol

import httpx

from nutrition_agent.config import Settings

# 被限速（429）或供應商暫時錯誤（5xx）時重試，等待 1、2、4、8 秒。
MAX_ATTEMPTS = 5
_RETRYABLE = frozenset({429, 500, 502, 503, 504})


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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._vlm_model = vlm_model
        self._llm_model = llm_model
        self._embedding_model = embedding_model
        self._provider = provider
        self._sleep = sleep
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
        response = self._post("/embeddings", {"model": self._embedding_model, "input": texts})
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]

    def _chat(self, model: str, messages: list[dict]) -> str:
        body: dict = {"model": model, "messages": messages}
        if self._provider:
            body["provider"] = {"order": [self._provider], "allow_fallbacks": False}
        response = self._post("/chat/completions", body)
        return response.json()["choices"][0]["message"]["content"]

    def _post(self, path: str, body: dict) -> httpx.Response:
        for attempt in range(MAX_ATTEMPTS):
            response = self._client.post(path, json=body)
            if response.status_code not in _RETRYABLE or attempt == MAX_ATTEMPTS - 1:
                break
            self._sleep(float(2**attempt))
        response.raise_for_status()
        return response
