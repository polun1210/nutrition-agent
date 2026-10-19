"""判定引擎（Seam B）：服用頻率、峰值與平均、跨產品加總、單位換算（#6）。"""

import pytest
from pydantic import ValidationError

from nutrition_agent.assessment import Intake, assess
from tests.assessment.conftest import line, make_case, product


def row(result, code):
    return next(c for c in result.ul_comparisons if c.nutrient_code == code)


def with_intake(prod, **intake):
    base = {"times_per_day": 1, "units_per_time": 1}
    return prod.model_copy(update={"intake": Intake(**{**base, **intake})})


def test_every_other_day_compares_peak_but_averages_half(ref):
    prod = with_intake(product("鎂片", [line("magnesium", 200)]), frequency="every_other_day")

    magnesium = row(assess(make_case(prod), ref), "magnesium")

    assert magnesium.intake == 200  # 峰值：服用當日
    assert magnesium.average_intake == 100
    assert magnesium.ul_percent == pytest.approx(200 / 350 * 100)
    assert magnesium.non_daily is True


def test_weekly_days_average_is_days_over_seven(ref):
    prod = with_intake(
        product("鈣片", [line("calcium", 700)]), frequency="weekly_days", days_per_week=2
    )

    calcium = row(assess(make_case(prod), ref), "calcium")

    assert calcium.intake == 700
    assert calcium.average_intake == 200


def test_cycle_average_is_on_days_over_cycle_length(ref):
    prod = with_intake(
        product("鈣片", [line("calcium", 700)]),
        frequency="cycle",
        cycle_on_days=5,
        cycle_off_days=2,
    )

    calcium = row(assess(make_case(prod), ref), "calcium")

    assert calcium.intake == 700
    assert calcium.average_intake == 500


def test_exceeded_uses_peak_even_when_average_is_below_limit(ref):
    # 每週 1 天吃 2500 mg 鈣：平均遠低於上限，但服用當日已達 100%
    prod = with_intake(
        product("鈣片", [line("calcium", 2500)]), frequency="weekly_days", days_per_week=1
    )

    calcium = row(assess(make_case(prod), ref), "calcium")

    assert calcium.exceeded is True
    assert calcium.average_intake < 400


def test_daily_product_has_average_equal_to_peak_and_is_not_non_daily(ref):
    calcium = row(assess(make_case(product("鈣片", [line("calcium", 500)])), ref), "calcium")

    assert calcium.average_intake == 500
    assert calcium.non_daily is False


def test_cross_product_sums_peaks_and_flags_when_only_total_exceeds(ref):
    # 單罐各 1500 mg 都沒超過 2500，加總 3000 才超過
    a = with_intake(product("鈣 A", [line("calcium", 1500)]), frequency="every_other_day")
    b = product("鈣 B", [line("calcium", 1500)])

    calcium = row(assess(make_case(a, b), ref), "calcium")

    assert calcium.intake == 3000
    assert calcium.exceeded is True
    assert calcium.average_intake == 2250
    assert calcium.non_daily is True


def test_iu_vitamin_d_converts_to_ug_before_comparing(ref):
    # 4000 IU = 100 ug（1 IU = 0.025 ug）
    vitamin_d = row(
        assess(make_case(product("D", [line("vitamin_d", 4000, "IU")])), ref), "vitamin_d"
    )

    assert vitamin_d.unit == "ug"
    assert vitamin_d.intake == 100


@pytest.mark.parametrize(
    "intake",
    [
        {"frequency": "as_needed"},
        {"frequency": "weekly_days"},
        {"frequency": "weekly_days", "days_per_week": 8},
        {"frequency": "cycle", "cycle_on_days": 3},
        {"frequency": "daily", "days_per_week": 3},
    ],
)
def test_intake_rejects_as_needed_and_malformed_parameters(intake):
    with pytest.raises(ValidationError):
        Intake(times_per_day=1, units_per_time=1, **intake)
