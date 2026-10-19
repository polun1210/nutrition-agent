import codecs
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


def test_空白註銷狀態且未過期的許可證保留():
    # 官方資料裡「有效」許可證的註銷狀態是空白，不是「未註銷」
    assert _export().lookup("某維他命錠") is not None


def test_已註銷與已過期的許可證被排除():
    table = _export()
    assert table.lookup("舊胃藥錠") is None
    assert table.lookup("ZANTAC TABLETS 150MG") is None
    assert table.lookup("過期降壓錠") is None  # 空白狀態但有效日期已過


def test_已廢止被排除():
    assert _export().lookup("廢止降壓錠") is None


def test_未知的非空白狀態一律排除_包含舊假設的未註銷():
    table = _export()
    assert table.lookup("未知狀態降壓錠") is None
    assert table.lookup("舊字面降壓錠") is None


def test_有效日期等於快照日當天仍保留(tmp_path):
    permits = tmp_path / "p.csv"
    permits.write_text(
        "許可證字號,註銷狀態,有效日期,中文品名,英文品名\nA,,2026/10/01,當天錠,\n",
        encoding="utf-8-sig",
    )
    table = export_drug_names(permits, FIXTURES / "ingredients_sample.csv", snapshot_date=SNAPSHOT)
    assert table.lookup("當天錠") is not None


def test_重複許可證與重複品名合併成分():
    entry = _export().lookup("合併測試錠")
    assert entry.ingredients == ("amlodipine", "famotidine")
    assert sum(e.name == "合併測試錠" for e in _export().entries) == 1


def test_可讀取UTF8_BOM檔案():
    assert (FIXTURES / "permits_sample.csv").read_bytes().startswith(codecs.BOM_UTF8)
    assert _export().lookup("脈優錠5毫克") is not None


def test_複方一對多():
    entry = _export().lookup("雅脈複方錠")
    assert entry.ingredients == ("amlodipine", "valsartan")


def test_處方標示是自由文字_不用來排除成分():
    # 「處方標示」官方是自由文字（約 6,936 種），沒有穩定的主成分／賦形劑語意；
    # 賦形劑只會多出範圍外成分（保守方向），不會被默默丟掉也不會變成範圍內。
    entry = _export().lookup("胃安錠")
    assert entry.ingredients == ("famotidine",)
    assert entry.out_of_scope == ("lactose", "some novel active")
    assert _export().lookup("合併測試錠").ingredients == ("amlodipine", "famotidine")


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


def test_成分檔缺少欄位時報錯(tmp_path):
    bad = tmp_path / "bad_ing.csv"
    bad.write_text("許可證字號,成分名稱\nX,Y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="缺少欄位"):
        export_drug_names(FIXTURES / "permits_sample.csv", bad, snapshot_date=SNAPSHOT)


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


@pytest.mark.parametrize(
    ("tfda_name", "code"),
    [
        # 2026-10-15 TFDA 處方成分資料裡的實際寫法（不是猜的鹽類名稱）
        ("METFORMIN HCL (EQ TO METFORMIN HYDROCHLORIDE)", "metformin"),
        ("HYDROCHLOROTHIAZIDE (EQ TO 3,4-DIHYDROCHLOROTHIAZIDE)", "hydrochlorothiazide"),
        ("ACETAMINOPHEN (EQ TO PARACETAMOL)", "acetaminophen"),
        ("LISINOPRIL (DIHYDRATE)", "lisinopril"),
        ("DAPAGLIFLOZIN PROPANEDIOL MONOHYDRATE", "dapagliflozin"),
        ("SODIUM RABEPRAZOLE", "rabeprazole"),
        ("AMLODIPINE (BESYLATE)", "amlodipine"),
        ("ZOLPIDEM HEMITARTRATE", "zolpidem"),
        ("CRYSTALLINE GLUCOSAMINE SULFATE", "glucosamine_sulfate"),
        ("INSULIN ICODEC", "insulin"),
        ("SACUBITRIL/VALSARTAN AS SACUBITRIL VALSARTAN SODIUM SALT COMPLEX", "valsartan"),
        ("MAGNESIUM ALUMINUM HYDROXIDE CO-DRIED GEL", "aluminum_magnesium_compound"),
        ("MAGALDRATE", "aluminum_magnesium_compound"),
        ("SYNTHETIC HYDROTALCITE", "aluminum_magnesium_compound"),
    ],
)
def test_真實資料的成分寫法對得到有效成分(tfda_name, code):
    from nutrition_agent.reference.drug_names import normalize_name

    assert load_aliases()[normalize_name(tfda_name)] == code


def test_常作賦形劑的鋁鎂矽酸鹽不算鋁鎂制酸劑():
    from nutrition_agent.reference.drug_names import normalize_name

    aliases = load_aliases()
    for name in ("ALUMINUM MAGNESIUM SILICATE", "MAGNESIUM ALUMINUM METASILICATE (NEUSILIN)"):
        assert normalize_name(name) not in aliases


def test_藥物目錄每個有效成分都有對照():
    codes = set(load_aliases().values())
    for ingredient in load_reference_data().drugs.ingredients:
        assert ingredient.code in codes, ingredient.code
