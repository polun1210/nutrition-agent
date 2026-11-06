"""結構化輸出的 schema 產生與寬鬆解析後備。"""

import pytest

from nutrition_agent.extraction.medication_pack import MedicationPackReading
from nutrition_agent.extraction.reading import VlmReading
from nutrition_agent.reporting.explanation import ExplanationReply
from nutrition_agent.structured import ResponseSchema, json_object_text


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


@pytest.mark.parametrize("model", [VlmReading, MedicationPackReading, ExplanationReply])
def test_由pydantic模型產生符合strict模式的schema(model):
    schema = ResponseSchema.from_model(model)

    assert schema.name == model.__name__
    nodes = list(walk(schema.schema))
    assert schema.schema["type"] == "object"
    assert not any("$ref" in n or "$defs" in n for n in nodes)
    assert not any("title" in n or "default" in n for n in nodes)
    for node in nodes:
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert sorted(node["required"]) == sorted(node["properties"])


def test_巢狀的成分列也展開成完整物件():
    rows = ResponseSchema.from_model(VlmReading).schema["properties"]["rows"]

    row = rows["items"]
    assert row["type"] == "object"
    assert row["properties"]["section"]["enum"] == ["nutrition_table", "ingredient_list", "per_unit_note"]


@pytest.mark.parametrize(
    "reply",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        '好的，結果如下：{"a": 1} 以上',
    ],
)
def test_寬鬆解析去掉code_fence並擷取大括號(reply):
    assert json_object_text(reply) == '{"a": 1}'


def test_沒有大括號時原樣交給呼叫端判定():
    assert json_object_text("抱歉我看不懂") == "抱歉我看不懂"
