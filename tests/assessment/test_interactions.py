"""交互作用判定（Seam B）：合成個案＋規則夾具；預期結果以規則 ID 表達。

真實 rules.toml 全是草稿，這裡不依賴它；夾具規則見 tests/fixtures/rules.toml。
"""

from nutrition_agent.assessment import assess
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

METFORMIN = drug("Glucophage", ("metformin", "biguanide"))
PPI = drug("Nexium", ("esomeprazole", "ppi"))


def finding(result, code):
    return next((f for f in result.interactions if f.ingredient_code == code), None)


def test_drug_affects_nutrient_triggers_without_supplement(fx_ref):
    case = make_case(medications=(METFORMIN,))

    result = assess(case, fx_ref)

    f = finding(result, "vitamin_b12")
    assert f.rule_ids == ["fx-metformin-b12"]
    assert [d.raw_name for d in f.triggering_drugs] == ["Glucophage"]
    assert f.advice == ["inform_provider"]
    assert f.supplemented is False


def test_only_approved_rules_fire(fx_ref):
    # statin→niacin 是草稿、thiazide→zinc 已退役；就算使用者補充了也不觸發
    case = make_case(
        product("綜合", [line("niacin", 20), line("zinc", 10)]),
        medications=(
            drug("Lipitor", ("atorvastatin", "statin")),
            drug("HCTZ", ("hydrochlorothiazide", "thiazide_diuretic")),
        ),
    )

    assert assess(case, fx_ref).interactions == []


def test_real_rules_are_all_drafts_so_nothing_fires(ref):
    case = make_case(product("鐵", [line("iron", 20)]), medications=(METFORMIN, PPI))

    result = assess(case, ref)

    assert result.interactions == []
    assert result.approved_rule_count == 0


def test_absorption_rule_needs_user_to_supplement_the_ingredient(fx_ref):
    antacid = drug("Gaviscon", ("aluminium_hydroxide", "calcium_magnesium_antacid"))

    without = assess(make_case(medications=(antacid,)), fx_ref)
    with_ca = assess(
        make_case(product("鈣", [line("calcium", 500)]), medications=(antacid,)), fx_ref
    )

    assert finding(without, "calcium") is None
    f = finding(with_ca, "calcium")
    assert f.rule_ids == ["fx-antacid-calcium-separate"]
    assert f.advice == ["separate_timing"]
    assert f.separation_hours == 2
    assert f.supplemented is True


def test_out_of_scope_and_unconfirmed_drugs_are_ignored(fx_ref):
    unconfirmed = drug("神秘藥", scope="unconfirmed")
    out = drug("Bisoprolol", ("metformin", "biguanide"), scope="out_of_scope")

    assert assess(make_case(medications=(unconfirmed, out)), fx_ref).interactions == []


def test_out_of_scope_and_unknown_ingredients_do_not_enter_rules(fx_ref):
    rule = make_rule(
        "r-q10",
        "biguanide",
        "coenzyme_q10",
        condition_type="drug_class",
        interaction_type="absorption",
        requires_supplement_intake=True,
    )
    case = make_case(
        product("Q10", [line("coenzyme_q10", 100)]),
        product("?", [line("unknown", 5)]),
        medications=(METFORMIN,),
    )

    assert assess(case, with_rules(fx_ref, rule)).interactions == []


def test_rule_with_ingredient_form_requires_matching_form(fx_ref):
    rule = make_rule(
        "r-form",
        "metformin",
        "magnesium",
        interaction_type="absorption",
        requires_supplement_intake=True,
        ingredient_form="oxide",
    )
    ref = with_rules(fx_ref, rule)

    def case_with(form):
        item = line("magnesium", 100).model_copy(update={"form": form})
        return make_case(product("鎂", [item]), medications=(METFORMIN,))

    assert assess(case_with("citrate"), ref).interactions == []
    assert assess(case_with(None), ref).interactions == []
    assert finding(assess(case_with("oxide"), ref), "magnesium").rule_ids == ["r-form"]


def test_multiple_rules_on_one_ingredient_make_one_card(fx_ref):
    r1 = make_rule("r-a", "ppi", "magnesium", condition_type="drug_class")
    r2 = make_rule(
        "r-b", "hydrochlorothiazide", "magnesium", advice="separate_timing", separation_hours=4
    )
    r3 = make_rule("r-c", "esomeprazole", "magnesium", advice="consult_before_combining")
    thiazide = drug("HCTZ", ("hydrochlorothiazide", "thiazide_diuretic"))
    case = make_case(medications=(PPI, thiazide))

    result = assess(case, with_rules(fx_ref, r1, r2, r3))

    assert len(result.interactions) == 1
    f = result.interactions[0]
    assert f.rule_ids == ["r-a", "r-b", "r-c"]
    assert [d.raw_name for d in f.triggering_drugs] == ["Nexium", "HCTZ"]
    assert f.advice == ["separate_timing", "inform_provider", "consult_before_combining"]
    assert f.separation_hours == 4
    assert f.reasons_zh == ["r-a 的說明文字。", "r-b 的說明文字。", "r-c 的說明文字。"]


def test_cards_follow_catalog_order(fx_ref):
    case = make_case(medications=(METFORMIN, PPI))

    codes = [f.ingredient_code for f in assess(case, fx_ref).interactions]

    assert codes == ["magnesium", "vitamin_b12"]  # 成分目錄：鎂在 B12 之前


def test_related_nutrient_card_lists_three_values_without_judging(fx_ref):
    case = make_case(medications=(METFORMIN,))

    f = finding(assess(case, fx_ref), "vitamin_b12")

    assert f.supplement_intake == 0
    assert f.recommended_total.value == 2.4
    assert f.recommended_total.kind == "RDA"
    assert f.ul is None  # B12 無已知上限攝取量
    assert f.unit == "ug"


def test_card_uses_actual_supplement_intake_when_taking_it(fx_ref):
    case = make_case(product("鎂", [line("magnesium", 100)]), medications=(PPI,))

    f = finding(assess(case, fx_ref), "magnesium")

    assert f.supplement_intake == 100
    assert f.ul == 350


def test_assessment_is_deterministic(fx_ref):
    case = make_case(product("鎂", [line("magnesium", 100)]), medications=(PPI, METFORMIN))

    assert assess(case, fx_ref) == assess(case, fx_ref)
    assert assess(case, fx_ref).model_dump_json() == assess(case, fx_ref).model_dump_json()
