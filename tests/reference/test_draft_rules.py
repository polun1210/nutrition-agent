"""#17：從語料草擬的候選規則，以及 2026-10-19 人工審查的結果。審定只能由開發者手動標記。

#40：agent 草擬的 Statin × 紅麴規則，等開發者審定（#46）。
"""

import pytest

from nutrition_agent.assessment import assess
from nutrition_agent.reference import (
    Advice,
    ConditionType,
    InteractionType,
    RuleSet,
    RuleStatus,
    SourceType,
    check_integrity,
    load_reference_data,
)
from nutrition_agent.reference.names import contains_quantity
from nutrition_agent.reporting.forbidden import find_forbidden_terms
from tests.assessment.conftest import drug, line, make_case, product


@pytest.fixture(scope="module")
def data():
    return load_reference_data()


@pytest.fixture(scope="module")
def rules(data):
    return data.rules.rules


def test_已草擬規則的最低數量(rules):
    assert len(rules) >= 10


APPROVED_IDS = {
    "metformin-vitamin-b12",
    "ppi-vitamin-b12",
    "h2-vitamin-b12",
    "ppi-magnesium",
    "ppi-iron",
    "thiazide-magnesium",
    "thiazide-potassium",
    "thiazide-zinc",
    "thiazide-vitamin-d",
    "acei-arb-potassium",
}
DRAFT_IDS = {"statin-red-yeast-rice"}
RETIRED_IDS = {
    "ppi-calcium",
    "atorvastatin-vitamin-d",
    "simvastatin-vitamin-d",
    "biguanide-niacin",
    "insulin-niacin",
}


def test_人工審查的結果與規則狀態一致(rules):
    by_status = {status: {r.id for r in rules if r.status is status} for status in RuleStatus}
    assert by_status[RuleStatus.APPROVED] == APPROVED_IDS
    assert by_status[RuleStatus.RETIRED] == RETIRED_IDS
    assert by_status[RuleStatus.DRAFT] == DRAFT_IDS
    for rule in rules:
        if rule.status is RuleStatus.APPROVED:
            assert rule.approved_by == "PolunChao", rule.id


@pytest.mark.parametrize("rule_id", sorted(RETIRED_IDS - {"ppi-calcium"}))
def test_高劑量才成立的規則已退役且說明寫明不核准(rules, rule_id):
    rule = next(r for r in rules if r.id == rule_id)
    assert rule.status is RuleStatus.RETIRED
    assert "不核准" in rule.reason_zh


def test_沒有_COX_2_選擇性抑制劑的規則(rules):
    assert not any(r.condition_code in {"cox2_inhibitor", "celecoxib", "etoricoxib"} for r in rules)


def test_PPI_鈣規則已退役且說明不再無條件宣稱降低吸收(rules):
    rule = next(r for r in rules if r.id == "ppi-calcium")
    assert rule.status is RuleStatus.RETIRED
    assert "降低鈣吸收" not in rule.reason_zh
    assert "不核准" in rule.reason_zh


def test_PPI_鈣規則即使其他規則全被審定也不會進入判定(data):
    live = tuple(
        r.model_copy(update={"status": RuleStatus.APPROVED, "approved_by": "test"})
        if r.status is RuleStatus.DRAFT
        else r
        for r in data.rules.rules
    )
    approved_ids = {r.id for r in RuleSet(version="t", rules=live).approved()}
    assert "ppi-calcium" not in approved_ids
    assert {"ppi-magnesium", "ppi-vitamin-b12", "ppi-iron"} <= approved_ids


def test_判定引擎只讀到審定規則(data):
    assert {r.id for r in data.rules.approved()} == APPROVED_IDS


def test_真實規則通過完整性檢查(data):
    assert check_integrity(data, data.rules) == []


def test_規則出處不含_Consumer_與_SUPP_AI(rules):
    # 出處類型由 SourceType 限定為 TFDA 仿單、NIH ODS HP 版、NCCIH fact sheet（ADR-0001）
    for rule in rules:
        for cite in rule.citations:
            assert "consumer" not in cite.document.casefold()
            assert "supp" not in cite.document.casefold()


def test_錯開時數只在原文明載時才填(rules):
    for rule in rules:
        if rule.separation_hours is not None:
            assert rule.advice.value == "separate_timing", rule.id


@pytest.mark.parametrize(
    ("condition", "ingredient"),
    [
        ("metformin", "vitamin_b12"),
        ("ppi", "vitamin_b12"),
        ("ppi", "magnesium"),
        ("thiazide_diuretic", "magnesium"),
        ("thiazide_diuretic", "potassium"),
        ("thiazide_diuretic", "zinc"),
        ("acei_arb", "potassium"),
    ],
)
def test_題目列舉的組合都有草稿(rules, condition, ingredient):
    assert any(r.condition_code == condition and r.ingredient_code == ingredient for r in rules)


RED_YEAST_RICE_FACT_SHEET = "sources/nccih/RedYeastRice-NCCIH.md"
RED_YEAST_RICE_QUOTES = (
    "Monacolin K is structurally identical to the medicine lovastatin",
    "Red yeast rice products that contain significant amounts of monacolin K can have the same potential "
    "side effects as statin drugs, including muscle, kidney, and liver damage",
    "Red yeast rice products can have the same types of drug interactions as statin drugs and therefore "
    "may interfere with certain medicines or increase the chance for side effects",
)


def statin_red_yeast_rice(rules):
    return next(r for r in rules if r.condition_code == "statin" and r.ingredient_code == "red_yeast_rice")


def test_Statin_紅麴是引用NCCIH原文的未審定草稿(rules):
    rule = statin_red_yeast_rice(rules)

    assert rule.status is RuleStatus.DRAFT
    assert rule.approved_by is None
    assert rule.condition_type is ConditionType.DRUG_CLASS
    assert rule.interaction_type is InteractionType.PHARMACODYNAMIC
    assert rule.requires_supplement_intake is True
    assert rule.advice is Advice.CONSULT_BEFORE_COMBINING
    assert rule.separation_hours is None
    assert [(c.source_type, c.document, c.quote) for c in rule.citations] == [
        (SourceType.NCCIH, RED_YEAST_RICE_FACT_SHEET, quote) for quote in RED_YEAST_RICE_QUOTES
    ]


def test_Statin_紅麴的審定說明不含數字與禁用詞(rules):
    reason = statin_red_yeast_rice(rules).reason_zh

    assert not contains_quantity(reason)
    assert find_forbidden_terms(reason) == []


def red_yeast_rice_finding(data, case):
    return next((f for f in assess(case, data).interactions if f.ingredient_code == "red_yeast_rice"), None)


def test_Statin_紅麴草稿審定前不進入判定_審定後提醒併用前先討論(data):
    case = make_case(
        product("紅麴膠囊", [line("red_yeast_rice", 600)]),
        medications=(drug("立普妥", ("atorvastatin", "statin")),),
    )

    assert red_yeast_rice_finding(data, case) is None

    # 模擬開發者審定（#46）：只改狀態與審定者，其他欄位照草稿
    signed = tuple(
        r.model_copy(update={"status": RuleStatus.APPROVED, "approved_by": "test"})
        if r.id == "statin-red-yeast-rice"
        else r
        for r in data.rules.rules
    )
    approved = data.model_copy(update={"rules": RuleSet(version="t", rules=signed)})
    finding = red_yeast_rice_finding(approved, case)
    assert finding.rule_ids == ["statin-red-yeast-rice"]
    assert finding.advice == ["consult_before_combining"]
    assert finding.separation_hours is None
