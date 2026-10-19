from datetime import date
from pathlib import Path

import pytest

from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.drug_names import (
    DrugNameEntry,
    DrugNameTable,
    check_drug_names,
    read_drug_names,
    write_drug_names,
)
from nutrition_agent.reference.tfda_export import export_drug_names, load_aliases

FIXTURES = Path(__file__).parent
SNAPSHOT = date(2026, 10, 1)


def _export():
    return export_drug_names(
        FIXTURES / "permits_sample.csv",
        FIXTURES / "ingredients_sample.csv",
        snapshot_date=SNAPSHOT,
    )


def test_有效許可證的中英文品名都對到有效成分():
    table = _export()
    assert table.lookup("脈優錠5毫克").ingredients == ("amlodipine",)
    assert table.lookup("norvasc tablets 5mg").ingredients == ("amlodipine",)


def test_已註銷與已過期的許可證被排除():
    table = _export()
    assert table.lookup("舊胃藥錠") is None
    assert table.lookup("ZANTAC TABLETS 150MG") is None
    assert table.lookup("過期降壓錠") is None


def test_複方一對多():
    entry = _export().lookup("雅脈複方錠")
    assert entry.ingredients == ("amlodipine", "valsartan")


def test_對不上的成分標成範圍外且賦形劑不算():
    entry = _export().lookup("胃安錠")
    assert entry.ingredients == ("famotidine",)
    assert entry.out_of_scope == ("some novel active",)


def test_只有範圍外成分的藥仍保留並無範圍內成分():
    entry = _export().lookup("某維他命錠")
    assert entry.ingredients == ()
    assert entry.out_of_scope == ("ascorbic acid",)


def test_快照日期是藥名表版本():
    assert _export().version == "2026-10-01"


def test_缺少欄位時報錯(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("許可證字號\nX\n", encoding="utf-8")
    with pytest.raises(ValueError, match="缺少欄位"):
        export_drug_names(bad, FIXTURES / "ingredients_sample.csv", snapshot_date=SNAPSHOT)


def test_寫出再載入內容相同(tmp_path):
    table = _export()
    path = tmp_path / "drug_names.csv"
    write_drug_names(table, path)
    assert read_drug_names(path) == table


def test_匯出結果通過完整性檢查且Ranitidine不在範圍內():
    table = _export()
    assert check_drug_names(table, load_reference_data().drugs) == []
    assert all("ranitidine" not in code for e in table.entries for code in e.ingredients)


def test_完整性檢查抓得到不在目錄的成分與Ranitidine():
    bad = DrugNameTable(
        version="x",
        entries=[
            DrugNameEntry(name="甲", lang="zh", ingredients=("nonexistent",)),
            DrugNameEntry(name="乙", lang="zh", ingredients=("ranitidine",)),
        ],
    )
    codes = {v.code for v in check_drug_names(bad, load_reference_data().drugs)}
    assert codes == {"unknown_ingredient", "ranitidine_in_scope"}


def test_成分對照表的目標都在有效成分目錄內():
    known = {i.code for i in load_reference_data().drugs.ingredients}
    assert set(load_aliases().values()) <= known
    assert not any("ranitidine" in k for k in load_aliases())
