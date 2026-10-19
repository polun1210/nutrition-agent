"""化合物比率表：每一列都附分子量計算式，數值要能用計算式驗證。"""

import pytest

from nutrition_agent.reference import IngredientCategory, check_integrity, load_reference_data
from nutrition_agent.reference.compounds import evaluate_expression
from nutrition_agent.reference.ingredients import normalize_name


@pytest.fixture(scope="module")
def data():
    return load_reference_data()


def _with_compound(data, compound):
    table = data.compounds.model_copy(update={"compounds": (compound,)})
    return data.model_copy(update={"compounds": table})


def test_table_covers_only_calcium_magnesium_iron(data):
    compounds = data.compounds.compounds
    assert 10 <= len(compounds) <= 20  # 15 種化合物，其中 3 種另列結晶水型態
    assert {c.nutrient_code for c in compounds} == {"calcium", "magnesium", "iron"}


def test_known_ratios_match_worked_examples(data):
    # 手算：CaCO3 = 40.078 / 100.087 = 0.4004；MgO = 24.305 / 40.304 = 0.6030；
    # 富馬酸亞鐵 FeC4H2O4 = 55.845 / 169.90 = 0.3287
    assert data.compounds.get("calcium_carbonate").element_ratio == pytest.approx(0.4004, abs=1e-4)
    assert data.compounds.get("magnesium_oxide").element_ratio == pytest.approx(0.6030, abs=1e-4)
    assert data.compounds.get("ferrous_fumarate").element_ratio == pytest.approx(0.3287, abs=1e-4)


def test_every_row_has_expressions_that_reproduce_its_ratio(data):
    for c in data.compounds.compounds:
        assert c.molecular_weight_expr.strip()
        assert c.element_mass_expr.strip()
        ratio = evaluate_expression(c.element_mass_expr) / evaluate_expression(
            c.molecular_weight_expr
        )
        assert c.element_ratio == pytest.approx(ratio, abs=5e-5), c.code


def test_find_by_chinese_or_english_name(data):
    assert data.compounds.find("檸檬酸鈣").nutrient_code == "calcium"
    assert data.compounds.find("Magnesium Oxide").code == "magnesium_oxide"
    assert data.compounds.find("葡萄糖酸鋅") is None  # 鋅不在表內


def test_nutrients_exist_in_ingredient_catalog_as_targets(data):
    for c in data.compounds.compounds:
        assert data.ingredients.get(c.nutrient_code).category is IngredientCategory.TARGET_NUTRIENT


def test_shipped_table_passes_integrity_check(data):
    assert check_integrity(data, data.rules) == []


def test_integrity_flags_ratio_that_does_not_match_its_expression(data):
    bad = data.compounds.compounds[0].model_copy(update={"element_ratio": 0.9})
    codes = {v.code for v in check_integrity(_with_compound(data, bad), data.rules)}
    assert "compound_ratio_mismatch" in codes


def test_integrity_flags_blank_expression(data):
    bad = data.compounds.compounds[0].model_copy(update={"molecular_weight_expr": " "})
    codes = {v.code for v in check_integrity(_with_compound(data, bad), data.rules)}
    assert "compound_expr_missing" in codes


def test_integrity_flags_nutrient_outside_calcium_magnesium_iron(data):
    bad = data.compounds.compounds[0].model_copy(update={"nutrient_code": "zinc"})
    codes = {v.code for v in check_integrity(_with_compound(data, bad), data.rules)}
    assert "compound_nutrient_unsupported" in codes


def test_expression_evaluator_is_arithmetic_only():
    assert evaluate_expression("2*(1.5+0.5)") == 4
    with pytest.raises(ValueError):
        evaluate_expression("__import__('os')")


@pytest.mark.parametrize(
    ("generic", "explicit_high", "explicit_low"),
    [
        ("硫酸亞鐵", "乾燥硫酸亞鐵", "七水硫酸亞鐵"),
        ("乳酸鈣", "無水乳酸鈣", "五水乳酸鈣"),
        ("磷酸氫鈣", "無水磷酸氫鈣", "二水磷酸氫鈣"),
    ],
)
def test_unspecified_hydrate_defaults_to_the_higher_ratio_form(
    data, generic, explicit_high, explicit_low
):
    # 標示沒寫結晶水型態時取比率較高者：超量檢查寧可多算，不要少算。
    default = data.compounds.find(generic)
    high = data.compounds.find(explicit_high)
    low = data.compounds.find(explicit_low)
    assert default == high
    assert low is not None and low.code != high.code
    assert high.element_ratio > low.element_ratio


def test_compound_names_are_unique_across_the_table(data):
    seen: dict[str, str] = {}
    for c in data.compounds.compounds:
        for name in (c.display_name_zh, *c.synonyms):
            key = normalize_name(name)
            assert seen.setdefault(key, c.code) == c.code, name
