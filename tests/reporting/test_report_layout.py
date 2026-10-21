"""報告版面的結構化資料（#23）：交互作用以藥為主角、上限比對表格、未評估成分與揭露字卡。"""

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.template import render_report
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

METFORMIN = drug("Glucophage", ("metformin", "biguanide"))
PPI = drug("Nexium", ("esomeprazole", "ppi"))
ANTACID = drug("Maalox", ("calcium_carbonate", "calcium_magnesium_antacid"))


def sections(case, ref):
    return {s.key: s for s in render_report(case, assess(case, ref), ref).sections}


def test_sections_in_reading_order(ref):
    report = render_report(case := make_case(product("鈣", [line("calcium", 500)])), assess(case, ref), ref)

    assert [s.key for s in report.sections] == [
        "interaction",
        "ul_comparison",
        "not_evaluated",
        "profile",
        "scope",
    ]


def test_interaction_grouped_by_drug_with_its_nutrients(fx_ref):
    calcium_rule = make_rule("r-ca", "ppi", "calcium", condition_type="drug_class")
    b12_rule = make_rule("r-b12", "metformin", "vitamin_b12")
    case = make_case(product("鈣片", [line("calcium", 500)]), medications=(METFORMIN, PPI))

    section = sections(case, with_rules(fx_ref, calcium_rule, b12_rule))["interaction"]

    groups = {g.drug: g for g in section.drug_groups}
    assert set(groups) == {"Glucophage", "Nexium"}
    assert groups["Glucophage"].drug_ingredients == ["Metformin"]
    assert groups["Glucophage"].ingredient_codes == ["vitamin_b12"]
    assert groups["Nexium"].ingredient_codes == ["calcium"]
    cards = {c.ingredient_code: c for c in section.cards}
    assert cards["calcium"].supplemented and cards["calcium"].products == ["鈣片"]
    # 沒有補充也會有卡片（藥影響體內營養素），措辭要能分辨
    assert not cards["vitamin_b12"].supplemented and cards["vitamin_b12"].products == []


def test_ul_comparison_as_table_rows_with_source_products(ref):
    case = make_case(product("鈣片", [line("calcium", 300)]), product("綜合維他命", [line("calcium", 200)]))

    section = sections(case, ref)["ul_comparison"]

    row = next(r for r in section.table if r.nutrient == "鈣")
    assert row.intake == "500 mg"
    assert row.ul == "2500 mg"
    assert row.percent == "20%"
    assert not row.exceeded
    assert row.products == ["鈣片", "綜合維他命"]
    assert "實際可能更高" in row.note or "上限" in row.note


def test_not_evaluated_section_separates_out_of_scope_and_unconfirmed(ref):
    case = make_case(product("Q10", [line("coenzyme_q10", 30)]), product("神秘粉", [line("unknown", 5)]))

    section = sections(case, ref)["not_evaluated"]

    neutral, warning = section.groups
    assert neutral.tone == "neutral" and "輔酶 Q10" in "".join(neutral.lines)
    assert warning.tone == "warning" and "藥師" in "".join(warning.lines)
    # 不再重複放在評估範圍與揭露
    assert "輔酶 Q10" not in "".join(sections(case, ref)["scope"].lines)


def test_not_evaluated_section_empty_when_everything_is_in_scope(ref):
    section = sections(make_case(product("鈣片", [line("calcium", 500)])), ref)["not_evaluated"]

    assert section.groups == [] and section.lines == []


def test_scope_disclosures_grouped_into_cards(ref):
    case = make_case(product("鈣片", [line("calcium", 500)]), medications=(ANTACID,))

    groups = {g.title: g for g in sections(case, ref)["scope"].groups}

    assert groups["特別提醒"].tone == "warning" and "制酸劑" in "".join(groups["特別提醒"].lines)
    assert "孕期" in "".join(groups["計算方式的限制"].lines)
    assert "16 類用藥" in "".join(groups["本系統涵蓋範圍"].lines)
