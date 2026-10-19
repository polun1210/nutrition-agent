"""揭露事項的觸發條件（Seam B）：由判定引擎決定，報告只渲染。"""

from nutrition_agent.assessment import Intake, Product, assess
from tests.assessment.conftest import drug, line, make_case, product

ANTACID = drug("Maalox", ("calcium_carbonate", "calcium_magnesium_antacid"))
ANTACID_OUT = drug(
    "某制酸劑", ("calcium_carbonate", "calcium_magnesium_antacid"), scope="out_of_scope"
)
METFORMIN = drug("Glucophage", ("metformin", "biguanide"))


def codes(case, ref):
    return assess(case, ref).disclosures


def every_other_day(name="隔天鈣"):
    return Product(
        name=name,
        dose_unit="粒",
        units_per_serving=1,
        ingredients=[line("calcium", 500)],
        intake=Intake(frequency="every_other_day", times_per_day=1, units_per_time=1),
    )


def test_healthy_population_only_when_a_condition_is_checked(ref):
    base = product("鈣", [line("calcium", 500)])

    assert "healthy_population" in codes(make_case(base, conditions=("hypertension",)), ref)
    assert "healthy_population" not in codes(make_case(base), ref)


def test_same_day_assumption_only_with_a_non_daily_product(ref):
    daily = product("鈣", [line("calcium", 500)])

    assert "same_day_assumption" not in codes(make_case(daily), ref)
    assert "same_day_assumption" in codes(make_case(daily, every_other_day()), ref)


def test_fixed_disclosures_are_always_present(ref):
    found = codes(make_case(product("鈣", [line("calcium", 500)])), ref)

    for code in ("scope_coverage", "medication_source_excluded", "pregnancy_lactation"):
        assert code in found


def test_antacid_reminder_needs_an_in_scope_calcium_magnesium_antacid(ref):
    base = product("鈣", [line("calcium", 500)])

    assert "antacid_reminder" in codes(make_case(base, medications=(ANTACID,)), ref)
    assert "antacid_reminder" not in codes(make_case(base, medications=(METFORMIN,)), ref)
    assert "antacid_reminder" not in codes(make_case(base, medications=(ANTACID_OUT,)), ref)
    assert "antacid_reminder" not in codes(make_case(base), ref)


def test_disclosures_are_deterministic(ref):
    case = make_case(every_other_day(), conditions=("hypertension",), medications=(ANTACID,))

    assert codes(case, ref) == codes(case, ref)
