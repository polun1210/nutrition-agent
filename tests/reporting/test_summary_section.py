"""報告「摘要」段落（#37）：報告最上方，由判定確定性地渲染，不經過 LLM。"""

import pytest

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.forbidden import find_forbidden_terms
from nutrition_agent.reporting.template import Group, render_report
from tests.assessment.conftest import drug, line, make_case, make_rule, product, with_rules

PPI = drug("Nexium", ("esomeprazole", "ppi"))
METFORMIN = drug("Glucophage", ("metformin", "biguanide"))


def summary(case, ref):
    report = render_report(case, assess(case, ref), ref)
    section = report.sections[0]
    assert section.key == "summary"
    return {g.title: g for g in section.groups}


def test_without_medications_summary_says_comparison_was_skipped(fx_ref):
    items = summary(make_case(product("鈣片", [line("calcium", 500)])), fx_ref)

    assert items["交互作用"].lines == ["你沒有提供用藥資料，未進行交互作用比對。"]
    assert items["交互作用"].count is None


def test_medications_without_hits_keep_the_not_no_interaction_wording(fx_ref):
    case = make_case(product("鐵", [line("iron", 20)]), medications=(PPI,))
    no_hit = with_rules(fx_ref, make_rule("r-x", "metformin", "zinc"))

    for reference, wording in ((no_hit, "未命中已審定的規則"), (with_rules(fx_ref), "尚無已審定的交互作用規則")):
        text = "".join(summary(case, reference)["交互作用"].lines)
        assert wording in text
        assert "這不表示兩者不會交互作用" in text
        assert summary(case, reference)["交互作用"].count is None


def test_hits_are_counted_and_named_with_a_prompt_to_ask_a_provider(fx_ref):
    # 夾具規則：metformin → 維生素 B12、PPI 類 → 鎂；兩張交互作用卡片
    case = make_case(product("鈣片", [line("calcium", 500)]), medications=(METFORMIN, PPI))

    item = summary(case, fx_ref)["交互作用"]

    assert item.tone == "warning"
    assert item.lines == ["2 件事要告訴醫師或藥師"]
    assert item.count == 2
    assert item.note is None


def test_exceeded_nutrients_are_named(fx_ref):
    # 鈣 3000 mg > 上限 2500 mg；鐵 50 mg > 上限 45 mg；鎂 100 mg 沒超過
    case = make_case(
        product("高鈣", [line("calcium", 3000), line("magnesium", 100)]),
        product("鐵劑", [line("iron", 50)]),
    )

    item = summary(case, fx_ref)["上限比對"]

    assert item.tone == "warning"
    assert item.lines == ["已超過上限：鈣、鐵"]
    assert item.count == 2


def test_no_exceeded_nutrient_is_stated_plainly(fx_ref):
    item = summary(make_case(product("鈣片", [line("calcium", 500)])), fx_ref)["上限比對"]

    assert item.tone == "neutral"
    assert item.lines == ["沒有營養素已超過上限"]
    assert item.count == 0


def test_unconfirmed_drugs_and_ingredients_are_counted_and_excluded(fx_ref):
    mystery_drug = drug("看不懂的藥", scope="unconfirmed")
    case = make_case(
        product("神秘粉", [line("unknown", 5), line("calcium", 500)]),
        product("Q10", [line("coenzyme_q10", 30)]),  # 範圍外不算無法確認
        medications=(mystery_drug,),
    )

    item = summary(case, fx_ref)["無法確認"]

    assert item.tone == "warning"
    assert item.lines == ["2 項無法確認的藥或成分，未納入判定"]
    assert item.count == 2


def test_unconfirmed_item_is_omitted_when_everything_is_known(fx_ref):
    case = make_case(product("Q10", [line("coenzyme_q10", 30)]), medications=(PPI,))

    assert list(summary(case, fx_ref)) == ["交互作用", "上限比對"]


def test_consult_findings_get_a_note_naming_them_in_stable_order(fx_ref):
    # 鎂（PPI）與維生素 B12（metformin）都改成「合併使用前先諮詢」，鈣維持告知
    rules = [
        make_rule("r-mg", "ppi", "magnesium", condition_type="drug_class", advice="consult_before_combining"),
        make_rule("r-b12", "metformin", "vitamin_b12", advice="consult_before_combining"),
        make_rule("r-ca", "metformin", "calcium"),
    ]
    case = make_case(product("鈣片", [line("calcium", 500)]), medications=(METFORMIN, PPI))

    item = summary(case, with_rules(fx_ref, *rules))["交互作用"]

    assert item.count == 3
    assert item.lines == ["3 件事要告訴醫師或藥師"]
    assert item.note == "其中 2 件，合併使用前請先問過：鎂、維生素 B12"


def test_legacy_group_without_count_or_note_still_loads():
    group = Group.model_validate({"title": "交互作用", "tone": "warning", "lines": ["舊文字"]})

    assert group.count is None and group.note is None


SCENARIOS = {
    "no_medication": lambda: make_case(product("鈣片", [line("calcium", 500)])),
    "no_hit": lambda: make_case(product("鐵", [line("iron", 20)]), medications=(PPI,)),
    "hit": lambda: make_case(product("鈣片", [line("calcium", 500)]), medications=(METFORMIN, PPI)),
    "exceeded": lambda: make_case(product("高鈣", [line("calcium", 3000)])),
    "unconfirmed": lambda: make_case(
        product("神秘粉", [line("unknown", 5)]), medications=(drug("看不懂的藥", scope="unconfirmed"),)
    ),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_summary_never_claims_safety_or_a_near_limit_state(fx_ref, name):
    case = SCENARIOS[name]()
    for reference in (fx_ref, with_rules(fx_ref)):
        section = render_report(case, assess(case, reference), reference).sections[0]
        text = "\n".join(section.lines)

        assert section.key == "summary" and text
        assert find_forbidden_terms(text) == []
        assert "沒有問題" not in text and "接近上限" not in text
