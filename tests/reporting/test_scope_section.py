"""報告「評估範圍與揭露」段落與禁用詞檢查（模板渲染，不經過 LLM）。"""

import pytest

from nutrition_agent.assessment import Intake, Product, assess
from nutrition_agent.reporting.forbidden import find_forbidden_terms
from nutrition_agent.reporting.template import render_report
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

ANTACID = drug("Maalox", ("calcium_carbonate", "calcium_magnesium_antacid"))
METFORMIN = drug("Glucophage", ("metformin", "biguanide"))


def render(case, ref):
    return render_report(case, assess(case, ref), ref)


def section_text(case, ref, key):
    report = render(case, ref)
    return "\n".join(next(s for s in report.sections if s.key == key).lines)


def full_text(report):
    parts = [line_ for s in report.sections for line_ in s.lines]
    for section in report.sections:
        for card in section.cards:
            parts.extend([card.ingredient, *card.drugs, *card.reasons, *card.advice])
            parts.extend(v.text for v in card.values)
    return "\n".join(parts)


def test_report_sections_in_reading_order(ref):
    report = render(make_case(product("鈣", [line("calcium", 500)])), ref)

    assert [s.title for s in report.sections] == [
        "交互作用",
        "上限比對",
        "本系統未評估的成分",
        "你的資料",
        "評估範圍與揭露",
    ]


def test_coverage_lists_conditions_classes_nutrients_and_uncovered_drugs(ref):
    text = section_text(make_case(product("鈣", [line("calcium", 500)])), ref, "scope")

    assert "5 種慢性病" in text and "高血壓" in text and "慢性失眠症" in text
    assert "16 類用藥" in text and "Statin 類" in text and "含鈣／含鎂制酸劑與軟便劑" in text
    assert "13 項營養素" in text and "維生素 B12" in text and "鉀" in text
    for uncovered in ("DPP-4 抑制劑", "磺醯脲類", "傳統 NSAIDs", "抗凝血與抗血小板藥", "骨鬆用藥"):
        assert uncovered in text
    assert "諮詢" in text


def test_fixed_disclosures_in_plain_report(ref):
    text = section_text(make_case(product("鈣", [line("calcium", 500)])), ref, "scope")

    assert "沒有計入藥品來源" in text
    assert "孕期" in text and "哺乳期" in text
    assert "健康族群" not in text
    assert "同一天服用" not in text


def test_healthy_population_and_same_day_assumption_when_triggered(ref):
    every_other = Product(
        name="隔天鈣",
        dose_unit="粒",
        units_per_serving=1,
        ingredients=[line("calcium", 500)],
        intake=Intake(frequency="every_other_day", times_per_day=1, units_per_time=1),
    )
    case = make_case(every_other, conditions=("hypertension",))

    text = section_text(case, ref, "scope")

    assert "健康族群" in text
    assert "同一天服用" in text


def test_antacid_gets_strong_reminder(ref):
    base = product("鈣", [line("calcium", 500)])

    with_antacid = section_text(make_case(base, medications=(ANTACID,)), ref, "scope")
    without = section_text(make_case(base, medications=(METFORMIN,)), ref, "scope")

    assert "制酸劑" in with_antacid and "特別提醒" in with_antacid
    assert "特別提醒" not in without


def test_out_of_scope_neutral_and_unconfirmed_warning(ref):
    case = make_case(
        product("Q10", [line("coenzyme_q10", 30)]),
        product("神秘粉", [line("unknown", 5)]),
    )

    text = section_text(case, ref, "not_evaluated")

    assert "輔酶 Q10" in text and "不在本系統評估範圍" in text
    assert "無法確認" in text and "藥師" in text


def test_fixed_wordings_in_profile(ref):
    base = product("鈣", [line("calcium", 500)])
    sick = section_text(make_case(base, conditions=("hypertension", "hyperlipidemia")), ref, "profile")
    none = section_text(make_case(base), ref, "profile")

    assert "你勾選了高血壓、高血脂" in sick
    assert "你未勾選本系統涵蓋的 5 種慢性病" in none
    assert "你沒有提供用藥資料" in none


SCENARIOS = {
    "plain": lambda: make_case(product("鈣", [line("calcium", 500)])),
    "sick_with_antacid": lambda: make_case(
        product("鈣", [line("calcium", 500)]),
        product("Q10", [line("coenzyme_q10", 30)]),
        product("神秘粉", [line("unknown", 5)]),
        conditions=("hypertension", "type2_diabetes"),
        medications=(ANTACID, METFORMIN),
    ),
    "over_limit": lambda: make_case(product("鈣", [line("calcium", 5000)])),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_report_never_contains_forbidden_terms(ref, name):
    case = SCENARIOS[name]()
    for reference in (ref, with_rules(ref, make_rule("r-x", "metformin", "vitamin_b12", reason_zh="這個藥可能影響體內這項維生素的狀態。"))):
        assert find_forbidden_terms(full_text(render(case, reference))) == []


def test_forbidden_term_checker_catches_safety_claims_and_instructions():
    bad = ["這樣很安全", "未發現問題", "你已確診", "建議每天服用 500 毫克", "請停用此藥", "請購買新的"]

    for text in bad:
        assert find_forbidden_terms(text), text
    assert find_forbidden_terms("錯開服用，至少相隔 2 小時") == []


def test_advice_to_people_taking_a_drug_is_not_an_instruction_to_take_it():
    """「建議服用此類藥物的人……」的「建議」對象是服藥的人，不是叫使用者服用。"""
    allowed = [
        "專家建議服用此類藥物的人應由醫療人員監測血鉀狀態。",
        "專家建議服用此類藥物者需要監測鉀的狀態。",
        "藥品仿單也建議服用含碳酸鈣的補充劑者，應與左旋甲狀腺素錯開服用時間。",
    ]
    still_forbidden = ["建議服用鈣片。", "我們建議服用此類藥物。", "建議服用維生素 D，可以補充不足。"]

    for text in allowed:
        assert find_forbidden_terms(text) == [], text
    for text in still_forbidden:
        assert find_forbidden_terms(text) == ["建議服用"], text


def test_describing_high_doses_from_evidence_is_not_dose_advice():
    """「高劑量菸鹼酸可能升高血糖」是在轉述證據，不是給劑量建議。"""
    allowed = [
        "高劑量的菸鹼酸可能提高血糖。",
        "較高劑量的菸鹼酸可能干擾糖尿病藥物的效果。",
        "服用大劑量菸鹼酸補充劑的人應監測血糖。",
    ]
    still_forbidden = [
        "可能需要調整藥物劑量。",
        "請依建議劑量服用。",
        "在推薦劑量下不會顯著影響。",
        "高劑量菸鹼酸可能升高血糖，可能需要調整劑量。",
    ]

    for text in allowed:
        assert find_forbidden_terms(text) == [], text
    for text in still_forbidden:
        assert find_forbidden_terms(text) == ["劑量"], text
