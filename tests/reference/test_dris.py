import pytest

from nutrition_agent.reference import (
    DriKind,
    IngredientCategory,
    Sex,
    UlScope,
    load_reference_data,
)


@pytest.fixture(scope="module")
def dris():
    return load_reference_data().dris


def test_51歲以上成人鎂UL是350毫克且涵蓋所有非食物來源(dris):
    ul = dris.lookup("magnesium", DriKind.UL, age=51, sex=Sex.FEMALE)
    assert ul.value == 350
    assert ul.unit == "mg"
    assert ul.ul_scope is UlScope.NON_FOOD


def test_維生素D的UL是50微克(dris):
    assert dris.lookup("vitamin_d", DriKind.UL, age=65, sex=Sex.MALE).value == 50
    assert dris.lookup("vitamin_d", DriKind.UL, age=65, sex=Sex.MALE).unit == "ug"


def test_鐵UL是40毫克且涵蓋補充劑與強化食品(dris):
    ul = dris.lookup("iron", DriKind.UL, age=40, sex=Sex.FEMALE)
    assert (ul.value, ul.ul_scope) == (40, UlScope.SUPPLEMENT_AND_FORTIFIED)


def test_鉀與B12沒有UL但仍有明確的紀錄(dris):
    for code in ("potassium", "vitamin_b12"):
        ul = dris.lookup(code, DriKind.UL, age=70, sex=Sex.MALE)
        assert ul is not None
        assert ul.value is None


def test_其他營養素的UL定義上含飲食(dris):
    ul = dris.lookup("zinc", DriKind.UL, age=30, sex=Sex.MALE)
    assert (ul.value, ul.ul_scope) == (35, UlScope.INCLUDES_DIET)


@pytest.mark.parametrize(
    ("code", "kind", "age", "sex", "value"),
    [
        ("magnesium", DriKind.RDA, 25, Sex.MALE, 380),
        ("magnesium", DriKind.RDA, 75, Sex.FEMALE, 300),
        ("iron", DriKind.RDA, 25, Sex.FEMALE, 15),
        ("iron", DriKind.RDA, 55, Sex.FEMALE, 10),
        ("vitamin_d", DriKind.AI, 40, Sex.FEMALE, 10),
        ("vitamin_d", DriKind.AI, 51, Sex.FEMALE, 15),
        ("potassium", DriKind.AI, 60, Sex.MALE, 2800),
        ("potassium", DriKind.AI, 60, Sex.FEMALE, 2500),
        ("vitamin_b12", DriKind.RDA, 80, Sex.MALE, 2.4),
        ("niacin", DriKind.RDA, 30, Sex.FEMALE, 14),
        ("vitamin_b6", DriKind.RDA, 71, Sex.MALE, 1.6),
        ("calcium", DriKind.AI, 19, Sex.MALE, 1000),
        ("selenium", DriKind.UL, 50, Sex.FEMALE, 400),
        ("niacin", DriKind.UL, 50, Sex.FEMALE, 35),
        ("folate", DriKind.UL, 50, Sex.FEMALE, 1000),
        ("vitamin_e", DriKind.UL, 50, Sex.FEMALE, 1000),
    ],
)
def test_抽查DRIs數值(dris, code, kind, age, sex, value):
    assert dris.lookup(code, kind, age=age, sex=sex).value == value


def test_成人資料列數與官方PDF核對一致(dris):
    # 2026-10-19 逐格對照官方 PDF：124/124 相符；列數變動代表資料被改過，需重新核對
    assert len(dris.entries) == 124


@pytest.mark.parametrize(
    ("code", "kind", "sex", "ages_and_values"),
    [
        ("magnesium", DriKind.RDA, Sex.MALE, [(30, 380), (31, 380), (50, 380), (51, 360), (70, 360), (71, 350)]),
        ("iron", DriKind.RDA, Sex.FEMALE, [(30, 15), (31, 15), (50, 15), (51, 10), (70, 10), (71, 10)]),
    ],
)
def test_年齡邊界取值(dris, code, kind, sex, ages_and_values):
    for age, value in ages_and_values:
        assert dris.lookup(code, kind, age=age, sex=sex).value == value, age


def test_性別分流_鐵19到30歲男女不同(dris):
    assert dris.lookup("iron", DriKind.RDA, age=19, sex=Sex.MALE).value == 10
    assert dris.lookup("iron", DriKind.RDA, age=19, sex=Sex.FEMALE).value == 15


def test_UL不分性別(dris):
    for code in ("magnesium", "iron", "zinc", "calcium"):
        male = dris.lookup(code, DriKind.UL, age=40, sex=Sex.MALE)
        female = dris.lookup(code, DriKind.UL, age=40, sex=Sex.FEMALE)
        assert male.value == female.value, code


def test_未滿19歲查不到(dris):
    assert dris.lookup("magnesium", DriKind.UL, age=18, sex=Sex.MALE) is None


def test_13項目標營養素在每個年齡組與性別都有建議量與UL():
    data = load_reference_data()
    targets = data.ingredients.by_category(IngredientCategory.TARGET_NUTRIENT)
    for ing in targets:
        for age in (19, 30, 31, 50, 51, 70, 71, 100):
            for sex in Sex:
                ref = [
                    data.dris.lookup(ing.code, k, age=age, sex=sex)
                    for k in (DriKind.RDA, DriKind.AI)
                ]
                assert sum(e is not None for e in ref) == 1, (ing.code, age, sex)
                assert data.dris.lookup(ing.code, DriKind.UL, age=age, sex=sex), (
                    ing.code,
                    age,
                    sex,
                )


def test_DRIs單位與成分目錄的標準單位一致_UL除外的葉酸():
    data = load_reference_data()
    for ing in data.ingredients.by_category(IngredientCategory.TARGET_NUTRIENT):
        for kind in (DriKind.RDA, DriKind.AI):
            entry = data.dris.lookup(ing.code, kind, age=40, sex=Sex.MALE)
            if entry:
                assert entry.unit == ing.canonical_unit
