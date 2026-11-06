"""結構化輸出（structured outputs）：由 pydantic 模型產生 strict 模式的 JSON schema，以及寬鬆解析後備。

strict schema 採各家都接受的最保守寫法：$ref 全部展開、每個物件 additionalProperties=false、
所有欄位都列為 required（可為 null 的欄位本身就是 anyOf [..., null]），並拿掉 title／default。
"""

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

_DROPPED_KEYS = frozenset({"title", "default"})
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


@dataclass(frozen=True)
class ResponseSchema:
    name: str
    schema: dict[str, Any]

    @classmethod
    def from_model(cls, model: type[BaseModel]) -> "ResponseSchema":
        raw = model.model_json_schema()
        defs = raw.pop("$defs", {})
        return cls(name=model.__name__, schema=_strict(raw, defs))


def _strict(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_strict(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _strict(defs[node["$ref"].rsplit("/", 1)[-1]], defs)
    result = {key: _strict(value, defs) for key, value in node.items() if key not in _DROPPED_KEYS}
    if result.get("type") == "object":
        result["additionalProperties"] = False
        result["required"] = list(result.get("properties", {}))
    return result


def json_object_text(reply: str) -> str:
    """寬鬆後備：去掉 code fence、擷取第一個 { 到最後一個 }；找不到就原樣回傳，讓呼叫端判定失敗。"""
    text = _FENCE.sub("", reply.strip())
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text
