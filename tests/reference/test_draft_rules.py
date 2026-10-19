"""#17：從語料草擬的候選規則。規則一律是草稿，審定只能由開發者手動標記。"""

import pytest

from nutrition_agent.reference import (
    RuleStatus,
    SourceType,
    check_integrity,
    load_reference_data,
)
from nutrition_agent.reference.names import contains_quantity_digit


@pytest.fixture(scope="module")
def data():
    return load_reference_data()


@pytest.fixture(scope="module")
def rules(data):
    return data.rules.rules


def test_說明文字可提到成分名稱中的數字但不可含量值():
    assert not contains_quantity_digit("這個藥可能降低維生素 B12 的吸收，也和 B6、n-3、Q10 有關。")
    assert contains_quantity_digit("每天補充 B12 超過 5 微克可能有影響。")
    assert contains_quantity_digit("服藥後 2 小時再吃維生素 B12。")


def test_已草擬規則的最低數量(rules):
    assert len(rules) >= 10


def test_真實規則一律是草稿且沒有審定者(rules):
    for rule in rules:
        assert rule.status is RuleStatus.DRAFT, rule.id
        assert rule.approved_by is None, rule.id


def test_agent_草擬的規則不會被判定引擎讀到(data):
    assert data.rules.approved() == ()


def test_草稿規則通過完整性檢查(data):
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
