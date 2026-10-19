"""交互作用卡片：結構化資料（前端卡片用）與沒有審定規則時的措辭。"""

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.template import render_report
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

METFORMIN = drug("Glucophage", ("metformin", "biguanide"))
PPI = drug("Nexium", ("esomeprazole", "ppi"))


def interaction_section(case, ref):
    report = render_report(case, assess(case, ref), ref)
    return next(s for s in report.sections if s.key == "interaction")


def test_each_finding_is_one_card_with_the_five_parts(fx_ref):
    section = interaction_section(make_case(medications=(METFORMIN,)), fx_ref)

    card = section.cards[0]
    assert card.ingredient == "維生素 B12"
    assert card.drugs == ["Glucophage"]
    assert "這個藥可能影響體內這項維生素的狀態。" in card.reasons
    assert card.advice == ["告知你的醫師或藥師"]
    assert [v.label for v in card.values] == ["來自補充劑", "建議總攝取量（含飲食）", "上限"]
    assert card.values[0].text == "0 ug"
    assert card.values[2].text == "無已知上限攝取量"


def test_card_per_ingredient_lists_all_triggering_drugs(fx_ref):
    r1 = make_rule("r-a", "ppi", "calcium", condition_type="drug_class")
    r2 = make_rule(
        "r-b", "hydrochlorothiazide", "calcium", advice="separate_timing", separation_hours=3
    )
    thiazide = drug("HCTZ", ("hydrochlorothiazide", "thiazide_diuretic"))

    section = interaction_section(
        make_case(medications=(PPI, thiazide)), with_rules(fx_ref, r1, r2)
    )

    assert len(section.cards) == 1
    assert section.cards[0].drugs == ["Nexium", "HCTZ"]
    assert "與藥物錯開服用，至少相隔 3 小時" in section.cards[0].advice


def test_no_approved_rules_gives_no_cards_and_no_claim_of_no_interaction(ref):
    case = make_case(product("鐵", [line("iron", 20)]), medications=(METFORMIN,))

    section = interaction_section(case, with_rules(ref))

    assert section.cards == []
    text = "\n".join(section.lines)
    assert "尚無已審定的交互作用規則" in text
    assert "沒有交互作用" not in text and "無交互作用" not in text
