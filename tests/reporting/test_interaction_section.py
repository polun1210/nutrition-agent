"""報告「交互作用」段落：模板由判定渲染成純文字卡片。"""

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.template import render_report
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

METFORMIN = drug("Glucophage", ("metformin", "biguanide"))
PPI = drug("Nexium", ("esomeprazole", "ppi"))
FORBIDDEN = ("沒有交互作用", "安全", "未發現")


def section_text(case, ref):
    report = render_report(case, assess(case, ref), ref)
    section = next(s for s in report.sections if s.key == "interaction")
    return "\n".join(section.lines)


def test_card_names_nutrient_drugs_reason_advice_and_three_values(fx_ref):
    text = section_text(make_case(medications=(METFORMIN,)), fx_ref)

    assert "維生素 B12" in text
    assert "因為你正在服用 Glucophage" in text
    assert "這個藥可能影響體內這項維生素的狀態。" in text
    assert "告知你的醫師或藥師" in text
    assert "來自補充劑 0 ug" in text
    assert "建議總攝取量（含飲食）2.4 ug" in text
    assert "無已知上限攝取量" in text
    assert "不足" not in text


def test_multiple_drugs_listed_and_separation_hours_shown(fx_ref):
    r1 = make_rule("r-a", "ppi", "calcium", condition_type="drug_class")
    r2 = make_rule(
        "r-b", "hydrochlorothiazide", "calcium", advice="separate_timing", separation_hours=3
    )
    thiazide = drug("HCTZ", ("hydrochlorothiazide", "thiazide_diuretic"))
    case = make_case(medications=(PPI, thiazide))

    text = section_text(case, with_rules(fx_ref, r1, r2))

    assert "因為你正在服用 Nexium 與 HCTZ" in text
    assert "錯開服用，至少相隔 3 小時" in text
    assert "告知你的醫師或藥師" in text


def test_no_approved_rules_never_says_no_interaction_or_safe(ref):
    case = make_case(product("鐵", [line("iron", 20)]), medications=(METFORMIN,))

    text = section_text(case, ref)

    assert "尚無已審定的交互作用規則" in text
    assert not any(word in text for word in FORBIDDEN)


def test_rules_exist_but_none_hit_still_not_claimed_safe(fx_ref):
    case = make_case(product("鐵", [line("iron", 20)]), medications=(PPI,))
    ref = with_rules(fx_ref, make_rule("r-x", "metformin", "zinc"))

    text = section_text(case, ref)

    assert "未命中已審定的規則" in text
    assert not any(word in text for word in FORBIDDEN)


def test_without_medications_says_comparison_was_skipped(fx_ref):
    text = section_text(make_case(product("鐵", [line("iron", 20)])), fx_ref)

    assert "你沒有提供用藥資料，未進行交互作用比對" in text
    assert "沒有交互作用" not in text
