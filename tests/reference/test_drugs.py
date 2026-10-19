from nutrition_agent.reference import DrugRole, load_reference_data


def test_共16個用藥類別其中10類規則型6類覆蓋型():
    drugs = load_reference_data().drugs
    assert len(drugs.classes) == 16
    assert len(drugs.by_role(DrugRole.RULE_BEARING)) == 10
    assert len(drugs.by_role(DrugRole.COVERAGE_ONLY)) == 6


def test_覆蓋型包含鈣離子阻斷劑與失眠用藥():
    drugs = load_reference_data().drugs
    coverage = {c.code for c in drugs.by_role(DrugRole.COVERAGE_ONLY)}
    assert {"ccb", "bzd_z_drug", "melatonin"} <= coverage


def test_有效成分可對映到所屬用藥類別():
    drugs = load_reference_data().drugs
    assert drugs.class_of("metformin") == "biguanide"
    assert drugs.class_of("omeprazole") == "ppi"
    assert drugs.class_of("magnesium_oxide") == "calcium_magnesium_antacid"
    assert drugs.class_of("no_such_drug") is None


def test_腸胃用藥獨立分組不隸屬疾病():
    drugs = load_reference_data().drugs
    ppi = drugs.get_class("ppi")
    assert ppi.group == "gastrointestinal"


def test_Ranitidine不在範圍內():
    drugs = load_reference_data().drugs
    assert drugs.class_of("ranitidine") is None
    assert all("ranitidine" not in i.code.lower() for i in drugs.ingredients)
    assert all("ranitidine" not in i.name_en.lower() for i in drugs.ingredients)


def test_資料帶版本號():
    assert load_reference_data().versions["drugs"]
