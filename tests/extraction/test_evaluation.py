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
COMPOUNDS = load_reference_data().compounds


@pytest.fixture(scope="module")
def catalog():
    return load_reference_data().ingredients


def score(reply: str, catalog) -> EvalReport:
    report = EvalReport()
    extraction = build_extraction([(1, parse_reading(reply))], catalog, COMPOUNDS)
    score_product(GOLD, extraction, report, catalog)
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


def test_每份量劑型單位與範圍內列都讀對時產品全對(catalog):
    report = score(RECORDED, catalog)

    assert report.fields["product_exact"].correct == 1
    assert report.fields["product_exact"].total == 1


def misread(**fields) -> str:
    """把錄製回應的頂層欄位換成讀錯的值。"""
    return json.dumps({**json.loads(RECORDED), **fields})


def test_每份量讀錯時產品不算全對(catalog):
    report = score(misread(serving_size=1), catalog)  # 每份 3 錠 → 1 錠

    assert report.fields["product_exact"].correct == 0
    assert report.summary()["amount"] == 1.0  # 列層級的含量正確率看不出來


def test_劑型單位讀錯時產品不算全對(catalog):
    report = score(misread(dose_unit="粒"), catalog)  # 錠 → 粒

    assert report.fields["product_exact"].correct == 0


def test_範圍內一列含量讀錯時產品不算全對(catalog):
    reading = json.loads(RECORDED)
    reading["rows"][6]["amount"] = 36  # 鈣 360 → 36

    report = score(json.dumps(reading), catalog)

    assert report.fields["product_exact"].correct == 0


def test_範圍內一列單位讀錯時產品不算全對(catalog):
    reading = json.loads(RECORDED)
    reading["rows"][6]["unit"] = "g"  # 鈣 360 mg → 360 g

    report = score(json.dumps(reading), catalog)

    assert report.fields["product_exact"].correct == 0


def test_範圍外的列讀錯不影響產品全對(catalog):
    reading = json.loads(RECORDED)
    reading["rows"][0]["amount"] = 30  # 維生素B1 不是目標營養素，金標準沒有標準代碼

    report = score(json.dumps(reading), catalog)

    assert report.summary()["amount"] < 1.0
    assert report.fields["product_exact"].correct == 1


def test_範圍內一列名稱讀錯時產品不算全對(catalog):
    reading = json.loads(RECORDED)
    reading["rows"][6]["raw_name"] = "鎂"  # 鈣 → 鎂，金標準的鈣這列等於沒讀到

    report = score(json.dumps(reading), catalog)

    assert report.fields["product_exact"].correct == 0


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

    summary = json.loads(result.stdout)
    assert summary["amount"] == 1.0
    assert summary["product_exact"] == 1.0
