"""藥名對照：TFDA 品名帶劑量與劑型，照片與自由輸入讀到的通常只有商品名或學名（#19）。"""

import pytest

from nutrition_agent.assessment.medications import resolve_medication, search_drugs
from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.drug_names import DrugNameEntry, DrugNameTable

# 寫法照真實 TFDA 匯出表
ENTRIES = [
    ("Crestor 5mg Film-Coated Tablets", "en", ("rosuvastatin",), ()),
    ("CRESTOR 10MG FILM-COATED TABLETS", "en", ("rosuvastatin",), ()),
    ("冠脂妥膜衣錠5毫克", "zh", ("rosuvastatin",), ()),
    ("脈優錠5毫克", "zh", ("amlodipine",), ()),
    ("脂脈優5毫克/10毫克", "zh", ("amlodipine", "atorvastatin"), ()),
    ("舒脈優膜衣錠 20/5/12.5毫克", "zh", ("amlodipine",), ("olmesartan medoxomil",)),
    ("Exforge film-coated tablet 5/80mg", "en", ("amlodipine", "valsartan"), ()),
    ("Exforge HCT Film Coated Tablets 5/160/12.5 mg", "en", ("amlodipine", "hydrochlorothiazide", "valsartan"), ()),
    ("NORVASC TABLETS 5MG", "en", ("amlodipine",), ()),
    ("金舒胃得腸溶膜衣錠20毫克", "zh", ("pantoprazole",), ()),
    ("Gisowed Gastro-Resistant Tablets 20 mg", "en", ("pantoprazole",), ()),
    ("Panadol Extra with Optizorb", "en", ("acetaminophen",), ("caffeine",)),
    ("Panadol Extra Caplets", "en", ("acetaminophen",), ("caffeine", "povidone")),
    ("Concor 5 mg film-coated tablets", "en", (), ("bisoprolol fumarate",)),
    ("Metformin", "en", ("metformin",), ()),
    ("Metformin Hydrochloride and Glimepiride Tablets", "en", ("metformin",), ("glimepiride",)),
    ("B Complex Tablets", "en", (), ("thiamine",)),
    ('SWELLIN TABLET "C.M."', "en", ("aluminum_hydroxide",), ()),
    ('"C.M." VIT. ANTI-COLD CAPSULES', "en", ("acetaminophen",), ()),
    # 品名就是學名、沒有處方成分資料的許可證（推測是原料藥），匯出後成分兩欄都空白（#59）
    ("Valsartan", "en", (), ()),
    ("Amlodipine Besilate", "en", (), ()),
    ("Pitavastatin calcium", "en", (), ()),
    ("Livalo Tablets 2mg", "en", (), ("pitavastatin calcium",)),
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


def test_開頭符合的品名優先於只是包含(table, catalog):
    # 「脈優」也出現在「脂脈優」「舒脈優」複方中間，但只有「脈優錠」是以它開頭（#20）
    medication = resolve_medication("脈優", table, catalog)

    assert medication.scope_status == "in_scope"
    assert codes(medication) == ["amlodipine"]


def test_開頭符合的候選成分組合不只一種時無法確認(table, catalog):
    # 「Exforge」開頭的有單方與加 HCT 的複方，交給使用者從搜尋選
    assert resolve_medication("Exforge", table, catalog).scope_status == "unconfirmed"


def test_開頭都對不到才用包含比對(table, catalog):
    assert codes(resolve_medication("Exforge HCT", table, catalog)) == ["amlodipine", "hydrochlorothiazide", "valsartan"]
    assert codes(resolve_medication("舒脈", table, catalog)) == ["amlodipine"]


def test_中英文商品名寫在一起時拆開各自對照(table, catalog):
    medication = resolve_medication("金舒胃得 Gisowed", table, catalog)

    assert medication.scope_status == "in_scope"
    assert codes(medication) == ["pantoprazole"]


@pytest.mark.parametrize("name", ['舒胃因錠 Swellin Tablet "C.M."', '舒胃因錠 Swellin “C.M.”'])
def test_拆開時略過引號裡的廠商簡稱(table, catalog, name):
    # TFDA 品名用引號標廠商，「"C.M."」不是藥名，不該拿去對照（#20）
    assert codes(resolve_medication(name, table, catalog)) == ["aluminum_hydroxide"]


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


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("VALSARTAN", ["valsartan"]),
        ("Valsartan 80", ["valsartan"]),
        ("VALSARTAN80", ["valsartan"]),
        ("Amlodipine", ["amlodipine"]),
        ("Amlodipine5", ["amlodipine"]),
        ("AMLODIPINE BESILATE", ["amlodipine"]),
    ],
)
def test_處方箋寫學名時以成分對照表對到有效成分(table, catalog, name, expected):
    # 處方箋多半直接寫學名；藥名表裡同名的條目沒有成分資料，不能據此判成範圍外（#59）
    medication = resolve_medication(name, table, catalog)

    assert medication.scope_status == "in_scope"
    assert codes(medication) == expected
    assert medication.raw_name == name


def test_學名對到時中文名用目錄的成分中文名(table, catalog):
    assert resolve_medication("VALSARTAN", table, catalog).name_zh == "纈沙坦"


def test_成分不明的條目不判成範圍外(table, catalog):
    # 「Pitavastatin calcium」條目成分不明；略過它之後，部分比對到的品名都是範圍外
    medication = resolve_medication("PITAVASTATIN CALCIUM", table, catalog)

    assert medication.scope_status == "out_of_scope"
    assert medication.out_of_scope_names == ["pitavastatin calcium"]


def test_只對到成分不明的條目就是無法確認(catalog):
    table = DrugNameTable(version="test", entries=[DrugNameEntry(name="Foozatan", lang="en", ingredients=())])

    assert resolve_medication("Foozatan", table, catalog).scope_status == "unconfirmed"


def test_搜尋候選裡成分不明的學名條目以成分對照表對照(table, catalog):
    found = {c.name: c for c in search_drugs("Valsartan", table, catalog)}

    assert found["Valsartan"].scope_status == "in_scope"
    assert [i.code for i in found["Valsartan"].ingredients] == ["valsartan"]
