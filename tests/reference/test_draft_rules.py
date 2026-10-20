"""#17：從語料草擬的候選規則，以及 2026-10-19 人工審查的結果。審定只能由開發者手動標記。"""

import pytest

from nutrition_agent.reference import (
    RuleSet,
    RuleStatus,
    SourceType,
    check_integrity,
    load_reference_data,
)


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
    assert by_status[RuleStatus.DRAFT] == set()
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


def test_規則出處只用_NIH_HP_或_TFDA_且不含_Consumer_與_SUPP_AI(rules):
    for rule in rules:
        for cite in rule.citations:
            assert cite.source_type in {SourceType.NIH_ODS_HP, SourceType.TFDA_LABEL}
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
