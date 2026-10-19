"""判定引擎（Seam B）：元素量來源有三種——標示載明、推估、無法判定；優先序依序遞減。

預期值用表內比率手算：檸檬酸鈣（四水）0.2108、氧化鎂 0.6030（見 compounds.toml 的計算式）。
"""

import pytest

from nutrition_agent.assessment import IngredientLine, assess
from tests.assessment.conftest import line, make_case, product


def compound_line(code, compound, amount, unit="mg") -> IngredientLine:
    return IngredientLine(
        ingredient_code=code, amount=amount, unit=unit, basis="compound", compound_code=compound
    )


def row(result, code):
    return next(c for c in result.ul_comparisons if c.nutrient_code == code)


def source(result, product_name, code):
    return next(
        s for s in result.nutrient_sources if (s.product_name, s.nutrient_code) == (product_name, code)
    )


def test_labeled_value_is_used_as_is_and_marked_labeled(ref):
    result = assess(make_case(product("鈣片", [line("calcium", 500)])), ref)

    assert row(result, "calcium").intake == 500
    assert row(result, "calcium").estimated is False
    assert source(result, "鈣片", "calcium").source == "labeled"


def test_compound_weight_is_estimated_by_element_ratio(ref):
    case = make_case(product("鈣片", [compound_line("calcium", "calcium_citrate_tetrahydrate", 1000)]))

    result = assess(case, ref)

    assert row(result, "calcium").intake == pytest.approx(210.8)
    assert row(result, "calcium").estimated is True
    estimated = source(result, "鈣片", "calcium")
    assert estimated.source == "estimated"
    assert estimated.compound_code == "calcium_citrate_tetrahydrate"
    assert result.undetermined_nutrients == []


def test_compound_weight_in_grams_is_converted_before_estimating(ref):
    case = make_case(product("鎂片", [compound_line("magnesium", "magnesium_oxide", 0.5, "g")]))

    assert row(assess(case, ref), "magnesium").intake == pytest.approx(301.5)  # 500 mg × 0.6030


def test_estimate_respects_daily_servings(ref):
    case = make_case(
        product("鈣片", [compound_line("calcium", "calcium_carbonate", 1000)], times_per_day=2)
    )

    assert row(assess(case, ref), "calcium").intake == pytest.approx(800.8)  # 2 × 1000 × 0.4004


def test_labeled_value_wins_over_compound_estimate_for_same_nutrient_in_a_product(ref):
    case = make_case(
        product(
            "綜合鈣片",
            [line("calcium", 150), compound_line("calcium", "calcium_citrate_tetrahydrate", 1000)],
        )
    )

    result = assess(case, ref)

    assert row(result, "calcium").intake == 150
    assert row(result, "calcium").estimated is False
    assert source(result, "綜合鈣片", "calcium").source == "labeled"


def test_labeled_and_estimated_products_sum_and_flag_estimated(ref):
    case = make_case(
        product("鈣片 A", [line("calcium", 500)]),
        product("鈣片 B", [compound_line("calcium", "calcium_citrate_tetrahydrate", 1000)]),
    )

    calcium = row(assess(case, ref), "calcium")

    assert calcium.intake == pytest.approx(710.8)
    assert calcium.estimated is True


def test_compound_not_chosen_is_undetermined_and_left_out_of_totals(ref):
    case = make_case(
        product("鈣片 A", [line("calcium", 500)]),
        product("鈣片 B", [compound_line("calcium", None, 1000)]),
    )

    result = assess(case, ref)

    assert result.undetermined_nutrients == ["calcium"]
    assert all(c.nutrient_code != "calcium" for c in result.ul_comparisons)
    assert source(result, "鈣片 B", "calcium").source == "undetermined"


def test_zinc_compound_is_undetermined_but_still_listed_as_present(ref):
    case = make_case(product("鋅片", [compound_line("zinc", None, 50)]))

    result = assess(case, ref)

    assert result.undetermined_nutrients == ["zinc"]
    assert result.ul_comparisons == []
    assert source(result, "鋅片", "zinc").source == "undetermined"


def test_compound_of_another_nutrient_is_undetermined(ref):
    case = make_case(product("怪片", [compound_line("calcium", "magnesium_oxide", 1000)]))

    assert assess(case, ref).undetermined_nutrients == ["calcium"]


def test_unconvertible_labeled_unit_is_still_undetermined(ref):
    case = make_case(product("鈣片", [line("calcium", 5, "IU")]))

    result = assess(case, ref)

    assert result.undetermined_nutrients == ["calcium"]
    assert source(result, "鈣片", "calcium").source == "undetermined"
