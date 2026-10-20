"""藥名對照：TFDA 品名帶劑量與劑型，照片與自由輸入讀到的通常只有商品名或學名（#19）。"""

import pytest

from nutrition_agent.assessment.medications import resolve_medication
from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.drug_names import DrugNameEntry, DrugNameTable

# 寫法照真實 TFDA 匯出表
ENTRIES = [
    ("Crestor 5mg Film-Coated Tablets", "en", ("rosuvastatin",), ()),
    ("CRESTOR 10MG FILM-COATED TABLETS", "en", ("rosuvastatin",), ()),
    ("冠脂妥膜衣錠5毫克", "zh", ("rosuvastatin",), ()),
    ("脈優錠5毫克", "zh", ("amlodipine",), ()),
    ("脈優立膜衣錠5/10毫克", "zh", ("amlodipine", "atorvastatin"), ()),
    ("NORVASC TABLETS 5MG", "en", ("amlodipine",), ()),
    ("金舒胃得腸溶膜衣錠20毫克", "zh", ("pantoprazole",), ()),
    ("Gisowed Gastro-Resistant Tablets 20 mg", "en", ("pantoprazole",), ()),
    ("Panadol Extra with Optizorb", "en", ("acetaminophen",), ("caffeine",)),
    ("Panadol Extra Caplets", "en", ("acetaminophen",), ("caffeine", "povidone")),
    ("Concor 5 mg film-coated tablets", "en", (), ("bisoprolol fumarate",)),
    ("Metformin", "en", ("metformin",), ()),
    ("Metformin Hydrochloride and Glimepiride Tablets", "en", ("metformin",), ("glimepiride",)),
    ("B Complex Tablets", "en", (), ("thiamine",)),
]


@pytest.fixture(scope="module")
def table():
    entries = [DrugNameEntry(name=n, lang=lang, ingredients=i, out_of_scope=o) for n, lang, i, o in ENTRIES]
    return DrugNameTable(version="test", entries=entries)


@pytest.fixture(scope="module")
def catalog():
    return load_reference_data().drugs


def codes(medication):
    return sorted(i.code for i in medication.ingredients)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Crestor", ["rosuvastatin"]),
        ("冠脂妥", ["rosuvastatin"]),
        ("norvasc", ["amlodipine"]),
        ("Panadol Extra", ["acetaminophen"]),
    ],
)
def test_品名不含劑量時以部分比對對照_候選成分相同就帶入(table, catalog, name, expected):
    medication = resolve_medication(name, table, catalog)

    assert medication.raw_name == name
    assert medication.scope_status == "in_scope"
    assert codes(medication) == expected


def test_逐字相符優先於部分比對(table, catalog):
    # 「Metformin」也是另一個複方品名的一部分，但有完全相符的品名時直接用它
    medication = resolve_medication("Metformin", table, catalog)

    assert codes(medication) == ["metformin"]
    assert medication.out_of_scope_names == []


def test_候選成分組合不只一種時無法確認(table, catalog):
    # 「脈優」同時是單方與 amlodipine＋atorvastatin 複方的品名一部分，交給使用者從搜尋選
    assert resolve_medication("脈優", table, catalog).scope_status == "unconfirmed"


def test_中英文商品名寫在一起時拆開各自對照(table, catalog):
    medication = resolve_medication("金舒胃得 Gisowed", table, catalog)

    assert medication.scope_status == "in_scope"
    assert codes(medication) == ["pantoprazole"]


def test_拆開後對到不同成分時無法確認(table, catalog):
    assert resolve_medication("Norvasc Crestor", table, catalog).scope_status == "unconfirmed"


def test_部分比對只回報所有候選都有的範圍外成分(table, catalog):
    medication = resolve_medication("Panadol Extra", table, catalog)

    assert medication.out_of_scope_names == ["caffeine"]


def test_目錄外的藥部分比對後是範圍外(table, catalog):
    medication = resolve_medication("Concor", table, catalog)

    assert medication.scope_status == "out_of_scope"
    assert medication.out_of_scope_names == ["bisoprolol fumarate"]


@pytest.mark.parametrize("name", ["B", "  ", "錠", "Tablets"])
def test_太短或太常見的字不做部分比對(table, catalog, name):
    assert resolve_medication(name, table, catalog).scope_status == "unconfirmed"


def test_查不到就是無法確認(table, catalog):
    medication = resolve_medication("善胃得", table, catalog)

    assert medication.scope_status == "unconfirmed"
    assert medication.ingredients == []


@pytest.mark.parametrize("name", ["Crestor®", "冠脂妥®", "CRESTOR™"])
def test_商標符號不影響對照(table, catalog, name):
    # 模型常照包裝把 ® 一起抄進來（實拍藥包 m32「Pantyl®」）
    assert codes(resolve_medication(name, table, catalog)) == ["rosuvastatin"]
