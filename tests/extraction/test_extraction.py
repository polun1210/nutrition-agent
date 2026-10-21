"""照片辨識後處理：VLM 回覆 → 確定性名稱標準化 → 多張照片合併。

模型閘道一律用假回應；回應內容取自 evals/vlm/recorded/vlm/（依 evals/vlm/gold 的 p01 整理）。
"""

import json
from pathlib import Path

import pytest

from nutrition_agent.extraction import build_extraction, parse_reading, read_label
from nutrition_agent.reference import load_reference_data
from tests.fakes import FakeGateway

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "evals" / "vlm" / "recorded" / "vlm"
GOLD = ROOT / "evals" / "vlm" / "gold"
UNREADABLE = json.dumps({"readable": False, "rows": []})


@pytest.fixture(scope="module")
def catalog():
    return load_reference_data().ingredients


def recorded(name: str) -> str:
    return (RECORDED / f"{name}.json").read_text(encoding="utf-8")


def rows_by_name(extraction):
    return {r.raw_name: r for r in extraction.rows}


def test_錄製回應的成分列與金標準逐列一致(catalog):
    gold = json.loads((GOLD / "p01.json").read_text(encoding="utf-8"))
    extraction = build_extraction([(1, parse_reading(recorded("p01-img01")))], catalog)

    rows = rows_by_name(extraction)
    quantified = [n for n in gold["nutrients"] if n["label_section"] != "ingredient_list"]
    for expected in quantified:
        row = rows[expected["raw_name"]]
        assert row.amount == expected["per_serving"], expected["raw_name"]
        if expected["scope_status"] == "in_scope":
            assert row.ingredient_code == expected["standard_code"], expected["raw_name"]
            assert row.scope_status == "in_scope"
        else:  # 金標準的範圍外 = 不評估；我們的目錄可能認得（範圍外）或不認得（無法確認）
            assert row.scope_status != "in_scope", expected["raw_name"]


def test_產品名稱與每份量取自包裝(catalog):
    extraction = build_extraction([(1, parse_reading(recorded("p01-img01")))], catalog)

    assert extraction.product_name == "挺立 葡萄糖胺強力錠"
    assert extraction.units_per_serving == 3
    assert extraction.dose_unit == "錠"


def test_名稱標準化以查表決定範圍狀態而不靠模型(catalog):
    extraction = build_extraction([(1, parse_reading(recorded("p01-img01")))], catalog)
    rows = rows_by_name(extraction)

    assert rows["鈣"].scope_status == "in_scope"
    assert rows["葡萄糖胺"].scope_status == "in_scope"  # 允許成分
    assert rows["維生素B1"].scope_status == "out_of_scope"  # 目錄內的範圍外成分
    assert rows["豬軟骨素硫酸鈉"].scope_status == "unconfirmed"  # 目錄查不到
    assert rows["豬軟骨素硫酸鈉"].ingredient_code is None


def test_單位寫法統一成目錄代碼(catalog):
    reply = json.dumps(
        {
            "readable": True,
            "rows": [
                {"raw_name": "鈣", "section": "nutrition_table", "amount": 1.2, "unit": "公克"},
                {"raw_name": "鎂", "section": "nutrition_table", "amount": 100, "unit": "毫克"},
                {"raw_name": "維生素D", "section": "nutrition_table", "amount": 5, "unit": "微克"},
                {"raw_name": "維生素E", "section": "nutrition_table", "amount": 9, "unit": "mg α-TE"},
            ],
        }
    )
    rows = rows_by_name(build_extraction([(1, parse_reading(reply))], catalog))

    assert [rows[n].unit for n in ("鈣", "鎂", "維生素D", "維生素E")] == [
        "g",
        "mg",
        "ug",
        "mg_alpha_te",
    ]


def test_讀不到的欄位留空而不猜(catalog):
    reply = json.dumps(
        {
            "readable": True,
            "rows": [
                {"raw_name": "鋅", "section": "nutrition_table", "readable": False},
                {"raw_name": "鐵", "section": "nutrition_table", "amount": 5, "unit": "mg"},
            ],
        }
    )
    extraction = build_extraction([(1, parse_reading(reply))], catalog)
    rows = rows_by_name(extraction)

    assert extraction.product_name is None
    assert extraction.units_per_serving is None
    assert extraction.dose_unit is None
    assert rows["鋅"].amount is None and rows["鋅"].unit is None
    assert rows["鋅"].readable is False


def test_整張讀不到時指出是哪一張並給拍攝提示(catalog):
    good = parse_reading(recorded("p01-img01"))
    bad = parse_reading(UNREADABLE)
    extraction = build_extraction([(7, good), (8, bad)], catalog)

    by_id = {p.photo_id: p for p in extraction.photos}
    assert by_id[7].readable is True and by_id[7].hint is None
    assert by_id[8].readable is False
    assert "重拍" in by_id[8].hint
    assert extraction.rows  # 讀得到的那張照樣有結果


def test_格式錯誤的模型回覆視為整張讀不到(catalog):
    for reply in ("抱歉我看不清楚", "{not json", json.dumps({"readable": True, "rows": "x"})):
        reading = parse_reading(reply)
        assert reading.readable is False


def test_模型回覆包在程式碼區塊也能解析():
    reading = parse_reading("```json\n" + recorded("p01-img01") + "\n```")
    assert reading.readable is True
    assert len(reading.rows) == 10


def test_多張照片合併成一筆且重複列只留一次(catalog):
    front = json.dumps(
        {
            "readable": True,
            "product_name": "家裡的鈣片",
            "rows": [{"raw_name": "鈣", "section": "nutrition_table", "amount": 500, "unit": "mg"}],
        }
    )
    back = json.dumps(
        {
            "readable": True,
            "serving_size": 2,
            "dose_unit": "粒",
            "rows": [
                {"raw_name": "鈣", "section": "nutrition_table", "amount": 500, "unit": "mg"},
                {"raw_name": "鎂", "section": "nutrition_table", "amount": 100, "unit": "mg"},
            ],
        }
    )
    extraction = build_extraction([(1, parse_reading(front)), (2, parse_reading(back))], catalog)

    assert extraction.product_name == "家裡的鈣片"
    assert extraction.units_per_serving == 2 and extraction.dose_unit == "粒"
    assert [r.raw_name for r in extraction.rows] == ["鈣", "鎂"]


def test_不認得的單位位數為無效的劑型單位時留空(catalog):
    reply = json.dumps({"readable": True, "serving_size": 1, "dose_unit": "capsule", "rows": []})
    extraction = build_extraction([(1, parse_reading(reply))], catalog)

    assert extraction.dose_unit is None
    assert extraction.units_per_serving == 1


def test_read_label把照片送給模型並解析回覆():
    gateway = FakeGateway(vision_reply=recorded("p01-img01"))

    reading = read_label(gateway, b"image-bytes", "image/jpeg")

    assert reading.product_name == "挺立 葡萄糖胺強力錠"
    assert gateway.calls[0][0] == "vision"



def test_營養標示固定欄位標記出來_成分列不受影響(catalog):
    reply = json.dumps({
        "readable": True,
        "product_name": "紅麴膠囊",
        "rows": [
            {"raw_name": "熱量", "section": "nutrition_table", "amount": 5, "unit": "kcal", "readable": True},
            {"raw_name": "鈉", "section": "nutrition_table", "amount": 1, "unit": "mg", "readable": True},
            {"raw_name": "紅麴", "section": "nutrition_table", "amount": 500, "unit": "mg", "readable": True},
            {"raw_name": "乳糖", "section": "ingredient_list", "amount": None, "unit": None, "readable": True},
        ],
    }, ensure_ascii=False)
    rows = rows_by_name(build_extraction([(1, parse_reading(reply))], catalog))

    assert rows["熱量"].nutrition_fact
    assert rows["鈉"].nutrition_fact
    assert not rows["紅麴"].nutrition_fact
    assert not rows["乳糖"].nutrition_fact
