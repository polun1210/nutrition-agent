import json

import httpx
import pytest

from nutrition_agent.gateway import MAX_ATTEMPTS, OpenRouterGateway
from nutrition_agent.structured import ResponseSchema

SCHEMA = ResponseSchema(name="Thing", schema={"type": "object", "properties": {}})


def _gateway(handler, **overrides) -> OpenRouterGateway:
    options = {
        "api_key": "k",
        "base_url": "https://example.test/api/v1",
        "vlm_model": "vendor/vlm-2026-01-01",
        "llm_model": "vendor/llm-2026-02-02",
        "embedding_model": "vendor/emb-2026-03-03",
    }
    options.update(overrides)
    return OpenRouterGateway(**options, transport=httpx.MockTransport(handler))


def test_complete_sends_configured_llm_model_and_returns_text():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "答"}}]})

    reply = _gateway(handler).complete("問", system="規則")

    assert reply == "答"
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "vendor/llm-2026-02-02"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "規則"}


def test_vision_sends_vlm_model_with_image_data_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    _gateway(handler).vision("讀標示", b"\x89PNG", "image/png")

    assert seen["body"]["model"] == "vendor/vlm-2026-01-01"
    parts = seen["body"]["messages"][-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_embed_returns_vectors_in_input_order():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "vendor/emb-2026-03-03"
        data = [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]
        return httpx.Response(200, json={"data": data})

    assert _gateway(handler).embed(["a", "b"]) == [[1.0], [2.0]]


def test_provider_setting_is_forwarded_when_present():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    _gateway(handler, provider="some-provider").complete("q")

    assert seen["body"]["provider"] == {"order": ["some-provider"], "allow_fallbacks": False}


def _capture():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    return seen, handler


def test_沒傳schema時請求不帶結構化輸出參數():
    seen, handler = _capture()
    gateway = _gateway(handler)

    gateway.complete("q")
    assert set(seen["body"]) == {"model", "messages"}
    gateway.vision("讀標示", b"png-bytes", "image/png")
    assert set(seen["body"]) == {"model", "messages"}


@pytest.mark.parametrize("call", ["complete", "vision"])
def test_有傳schema時帶上json_schema並只路由到支援的供應商(call):
    seen, handler = _capture()
    gateway = _gateway(handler)

    if call == "complete":
        gateway.complete("q", system="s", schema=SCHEMA)
    else:
        gateway.vision("讀標示", b"png-bytes", "image/png", schema=SCHEMA)

    assert seen["body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Thing", "strict": True, "schema": SCHEMA.schema},
    }
    assert seen["body"]["provider"] == {"require_parameters": True}


def test_schema與指定供應商的設定合併():
    seen, handler = _capture()

    _gateway(handler, provider="some-provider").complete("q", schema=SCHEMA)

    assert seen["body"]["provider"] == {
        "order": ["some-provider"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }


def _flaky(statuses: list[int]):
    """依序回傳指定狀態碼，最後一次回 200（embedding 格式）。"""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        status = statuses[len(calls) - 1] if len(calls) <= len(statuses) else 200
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    return handler, calls


def test_rate_limited_and_server_errors_are_retried_with_backoff():
    handler, calls = _flaky([429, 503])
    waits: list[float] = []

    vectors = _gateway(handler, sleep=waits.append).embed(["a"])

    assert vectors == [[1.0]]
    assert len(calls) == 3
    assert waits == [1.0, 2.0]


def test_client_errors_are_not_retried():
    handler, calls = _flaky([400])

    with pytest.raises(httpx.HTTPStatusError):
        _gateway(handler, sleep=lambda _: None).embed(["a"])
    assert len(calls) == 1


def test_gives_up_after_max_attempts():
    handler, calls = _flaky([429] * 10)

    with pytest.raises(httpx.HTTPStatusError):
        _gateway(handler, sleep=lambda _: None).complete("q")
    assert len(calls) == MAX_ATTEMPTS


def test_api_的模型閘道整個程序共用一個實例():
    from nutrition_agent.api.deps import get_gateway

    # 每個請求新建一個沒關閉的 HTTP client 會漏連線；共用的 httpx.Client 可跨執行緒使用。
    assert get_gateway() is get_gateway()
