"""模型回覆解析失敗時保留「讀不到」的行為，並留下警告紀錄方便追查。"""

import logging

import pytest

from nutrition_agent.extraction.medication_pack import parse_pack_reading
from nutrition_agent.extraction.reading import parse_reading


@pytest.mark.parametrize("parse", [parse_reading, parse_pack_reading])
def test_unparseable_reply_is_unreadable_and_logged(parse, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        reading = parse("這不是 JSON")
    assert reading.readable is False
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.parametrize("parse", [parse_reading, parse_pack_reading])
def test_schema_mismatch_is_unreadable_and_logged(parse, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        reading = parse('{"readable": "也許", "rows": 3, "names": 3}')
    assert reading.readable is False
    assert any(r.levelno == logging.WARNING for r in caplog.records)
