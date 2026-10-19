"""判定引擎（Seam B）：評估個案快照＋參考資料 → 判定。純函數，合成個案。

DRIs 預期值是從 reference/data/dris.csv 抄的字面值（71 歲以上：鈣 UL 2500 mg、鎂 UL 350 mg）。
"""

from nutrition_agent.assessment import assess
from tests.assessment.conftest import line, make_case, product


def row(result, code):
    return next(c for c in result.ul_comparisons if c.nutrient_code == code)


def test_single_product_reports_percent_of_ul(ref):
    case = make_case(product("鈣片", [line("calcium", 500)]))

    result = assess(case, ref)

    calcium = row(result, "calcium")
    assert calcium.intake == 500
    assert calcium.unit == "mg"
    assert calcium.ul == 2500
    assert calcium.ul_percent == 20
    assert calcium.exceeded is False


def test_daily_intake_converts_dose_units_to_servings_including_fractions(ref):
    # 每份 2 粒含鎂 100 mg；每天 2 次、每次 1.5 粒 → 3 粒 = 1.5 份 → 150 mg
    case = make_case(
        product("鎂片", [line("magnesium", 100)], serving=2, times_per_day=2, per_time=1.5)
    )

    magnesium = row(assess(case, ref), "magnesium")

    assert magnesium.intake == 150
    assert magnesium.ul_percent == 150 / 350 * 100


def test_thirds_do_not_lose_precision_at_the_limit(ref):
    # 每份 3 粒含鎂 350 mg；每天吃 3 粒 → 剛好 1 份 → 100%
    case = make_case(product("鎂片", [line("magnesium", 350)], serving=3, per_time=3))

    magnesium = row(assess(case, ref), "magnesium")

    assert magnesium.ul_percent == 100
    assert magnesium.exceeded is True


def test_one_third_of_a_serving_per_day_is_exact(ref):
    # 每份 3 粒含鈣 2400 mg，每天 1 粒 → 800 mg（浮點的 2400 * (1/3) 會差一點）
    case = make_case(product("鈣片", [line("calcium", 2400)], serving=3))

    assert row(assess(case, ref), "calcium").intake == 800


def test_sums_same_nutrient_across_products_and_flags_exceeded_at_100(ref):
    case = make_case(
        product("鈣片 A", [line("calcium", 1500)]),
        product("綜合維他命", [line("calcium", 1000), line("zinc", 10)]),
    )

    result = assess(case, ref)

    calcium = row(result, "calcium")
    assert calcium.intake == 2500
    assert calcium.ul_percent == 100
    assert calcium.exceeded is True
    assert row(result, "zinc").exceeded is False


def test_just_under_limit_is_not_flagged(ref):
    case = make_case(product("鈣片", [line("calcium", 2499.9)]))

    assert row(assess(case, ref), "calcium").exceeded is False


def test_nutrient_without_ul_has_no_percent_and_is_never_exceeded(ref):
    case = make_case(product("鉀", [line("potassium", 99999)]))

    potassium = row(assess(case, ref), "potassium")

    assert potassium.ul is None
    assert potassium.ul_percent is None
    assert potassium.exceeded is False


def test_magnesium_and_iron_are_marked_supplement_only(ref):
    case = make_case(product("綜合", [line("magnesium", 100), line("iron", 10), line("zinc", 5)]))

    result = assess(case, ref)

    assert row(result, "magnesium").supplement_only is True
    assert row(result, "iron").supplement_only is True
    assert row(result, "zinc").supplement_only is False


def test_ul_comparison_uses_dris_group_for_age_and_sex(ref):
    # 鐵 UL 40 mg：30 mg 為 75%
    case = make_case(product("鐵劑", [line("iron", 30)]), sex="male")

    assert row(assess(case, ref), "iron").ul_percent == 75


def test_other_units_are_converted_to_dris_units(ref):
    # 維生素 D 800 IU → 20 ug（換算表 IU→ug）
    case = make_case(product("D3", [line("vitamin_d", 800, unit="IU")]))

    vitamin_d = row(assess(case, ref), "vitamin_d")

    assert vitamin_d.unit == "ug"
    assert vitamin_d.intake == 20


def test_unconvertible_units_are_left_out_and_reported(ref):
    case = make_case(product("奇怪單位", [line("calcium", 5, unit="mg_alpha_te")]))

    result = assess(case, ref)

    assert result.ul_comparisons == []
    assert result.undetermined_nutrients == ["calcium"]


def test_out_of_scope_and_unconfirmed_ingredients_are_kept_not_compared(ref):
    case = make_case(
        product("綜合", [line("coenzyme_q10", 30), line("unknown", 5), line("red_yeast_rice", 600)])
    )

    result = assess(case, ref)

    assert [i.ingredient_code for i in result.out_of_scope_ingredients] == ["coenzyme_q10"]
    assert [i.ingredient_code for i in result.unconfirmed_ingredients] == ["unknown"]
    assert result.ul_comparisons == []


def test_comparisons_follow_catalog_order(ref):
    case = make_case(product("綜合", [line("zinc", 5), line("calcium", 100), line("iron", 5)]))

    codes = [c.nutrient_code for c in assess(case, ref).ul_comparisons]

    assert codes == ["calcium", "iron", "zinc"]


def test_same_case_gives_identical_result(ref):
    case = make_case(product("鈣片", [line("calcium", 333), line("zinc", 7)], serving=3))

    assert assess(case, ref) == assess(case, ref)


def test_any_chronic_condition_discloses_healthy_population_basis(ref):
    sick = make_case(product("鈣", [line("calcium", 1)]), conditions=["hypertension"])
    healthy = make_case(product("鈣", [line("calcium", 1)]))

    assert "healthy_population" in assess(sick, ref).disclosures
    assert "healthy_population" not in assess(healthy, ref).disclosures
