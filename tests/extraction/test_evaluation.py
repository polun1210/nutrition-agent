"""VLM eval 的比對邏輯：用錄製回應重播，不打外部 API。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nutrition_agent.extraction import build_extraction, parse_reading
from nutrition_agent.extraction.evaluation import EvalReport, score_product
from nutrition_agent.reference import load_reference_data

ROOT = Path(__file__).resolve().parents[2]
GOLD = json.loads((ROOT / "evals/vlm/gold/p01.json").read_text(encoding="utf-8"))
RECORDED = (ROOT / "evals/vlm/recorded/vlm/p01-img01.json").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def catalog():
    return load_reference_data().ingredients


def score(reply: str, catalog) -> EvalReport:
    report = EvalReport()
    score_product(GOLD, build_extraction([(1, parse_reading(reply))], catalog), report, catalog)
    return report


def test_錄製回應各欄位與金標準一致(catalog):
    summary = score(RECORDED, catalog).summary()

    for name in ("product_name", "serving_size", "dose_unit", "amount", "unit", "scope_status"):
        assert summary[name] == 1.0, name
    assert summary["standard_code"] == 1.0
    assert summary["row_precision"] == 1.0
    assert 0 < summary["row_recall"] < 1  # 錄製回應只有成分欄的一列，其餘成分欄的列沒讀


def test_欄位讀錯時對應的正確率下降(catalog):
    wrong = json.loads(RECORDED)
    wrong["product_name"] = "別的產品"
    wrong["rows"][6]["amount"] = 36  # 鈣 360 → 36

    summary = score(json.dumps(wrong), catalog).summary()

    assert summary["product_name"] == 0.0
    assert 0 < summary["amount"] < 1.0
    assert summary["unit"] == 1.0


def test_成分欄沒有含量的目標營養素不計範圍與代碼評分(catalog):
    # 金標準舊慣例把成分欄的目標營養素標成範圍外，查表會判範圍內；這些列不進入評估，只算讀到與否
    base = score(RECORDED, catalog)
    reading = json.loads(RECORDED)
    reading["rows"] += [
        {"raw_name": "菸鹼醯胺", "section": "ingredient_list", "amount": None, "unit": None, "readable": True},
        {"raw_name": "葡萄糖胺鹽酸鹽", "section": "ingredient_list", "amount": None, "unit": None, "readable": True},
    ]

    report = score(json.dumps(reading), catalog)

    assert report.matched_rows == base.matched_rows + 2
    assert report.summary()["scope_status"] == 1.0
    assert report.summary()["standard_code"] == 1.0
    # 允許成分只看有沒有，成分欄的列照常評分
    assert report.fields["scope_status"].total == base.fields["scope_status"].total + 1


def test_整張讀不到時列召回為零(catalog):
    summary = score(json.dumps({"readable": False}), catalog).summary()

    assert summary["row_recall"] == 0.0
    assert summary["product_name"] == 0.0


def test_命令列重播錄製回應並印出各欄位正確率():
    result = subprocess.run(
        [sys.executable, str(ROOT / "evals/vlm/run.py"), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        check=True,
    )

    assert json.loads(result.stdout)["amount"] == 1.0
