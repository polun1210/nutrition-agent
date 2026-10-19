from pathlib import Path

import pytest
from pydantic import ValidationError

from nutrition_agent.reference import (
    RuleStatus,
    check_integrity,
    load_reference_data,
    load_rule_set,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "rules.toml"


@pytest.fixture(scope="module")
def data():
    return load_reference_data()


@pytest.fixture(scope="module")
def fixture_rules():
    return load_rule_set(FIXTURE)


def raw_rule(fixture_rules, rule_id: str) -> dict:
    rule = next(r for r in fixture_rules.rules if r.id == rule_id)
    return rule.model_dump(mode="json")


def codes(violations) -> set[str]:
    return {v.code for v in violations}


# ---- 資料格式與狀態 ----


def test_夾具含草稿審定退役三種狀態(fixture_rules):
    assert {r.status for r in fixture_rules.rules} == set(RuleStatus)


def test_判定引擎只讀審定規則(fixture_rules):
    approved = fixture_rules.approved()
    assert {r.id for r in approved} == {
        "fx-metformin-b12",
        "fx-ppi-magnesium",
        "fx-antacid-calcium-separate",
    }


def test_真實規則檔載得進來且帶版本號(data):
    assert data.versions["rules"]
    assert data.versions["dris"] and data.versions["units"]


# ---- 單條規則的不變式（建構時就擋）----


def test_藥物影響營養素不能要求使用者有補充(fixture_rules):
    bad = raw_rule(fixture_rules, "fx-metformin-b12") | {"requires_supplement_intake": True}
    with pytest.raises(ValidationError):
        type(fixture_rules.rules[0]).model_validate(bad)


def test_其他兩類交互作用必須要求使用者有補充(fixture_rules):
    bad = raw_rule(fixture_rules, "fx-statin-niacin-draft") | {"requires_supplement_intake": False}
    with pytest.raises(ValidationError):
        type(fixture_rules.rules[0]).model_validate(bad)


def test_錯開服用一定有時數且只有錯開服用有時數(fixture_rules):
    rule_cls = type(fixture_rules.rules[0])
    no_hours = raw_rule(fixture_rules, "fx-antacid-calcium-separate") | {"separation_hours": None}
    with pytest.raises(ValidationError):
        rule_cls.model_validate(no_hours)
    stray_hours = raw_rule(fixture_rules, "fx-ppi-magnesium") | {"separation_hours": 2}
    with pytest.raises(ValidationError):
        rule_cls.model_validate(stray_hours)


def test_建議行動只能是三種封閉選項之一(fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium") | {"advice": "stop_taking"}
    with pytest.raises(ValidationError):
        type(fixture_rules.rules[0]).model_validate(bad)


@pytest.mark.parametrize("text", ["每日不要超過 350 毫克。", "請間隔二小時，共 2 次", "上限為３５０"])
def test_規則說明文字不得含數字(fixture_rules, text):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium") | {"reason_zh": text}
    if any(ch.isdigit() for ch in text):
        with pytest.raises(ValidationError):
            type(fixture_rules.rules[0]).model_validate(bad)


def test_審定規則必須有審定者而草稿不能有(fixture_rules):
    rule_cls = type(fixture_rules.rules[0])
    unsigned = raw_rule(fixture_rules, "fx-ppi-magnesium") | {"approved_by": None}
    with pytest.raises(ValidationError):
        rule_cls.model_validate(unsigned)
    signed_draft = raw_rule(fixture_rules, "fx-statin-niacin-draft") | {"approved_by": "someone"}
    with pytest.raises(ValidationError):
        rule_cls.model_validate(signed_draft)


def test_規則至少一筆出處且引文不能空白(fixture_rules):
    rule_cls = type(fixture_rules.rules[0])
    with pytest.raises(ValidationError):
        rule_cls.model_validate(raw_rule(fixture_rules, "fx-ppi-magnesium") | {"citations": []})
    blank = raw_rule(fixture_rules, "fx-ppi-magnesium")
    blank["citations"][0]["quote"] = "  "
    with pytest.raises(ValidationError):
        rule_cls.model_validate(blank)


def test_出處類型只能是三種(fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["source_type"] = "nih_ods_consumer"
    with pytest.raises(ValidationError):
        type(fixture_rules.rules[0]).model_validate(bad)


# ---- 跨檔完整性檢查 ----


def test_真實參考資料通過所有完整性檢查(data):
    assert check_integrity(data, data.rules) == []


def test_夾具規則通過完整性檢查(data, fixture_rules):
    assert check_integrity(data, fixture_rules) == []


def test_出處引文必須逐字存在於語料(data, fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["quote"] = "PPIs always cause hypomagnesemia within a week"
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert codes(check_integrity(data, rules)) == {"quote_not_in_corpus"}


def test_引文比對容忍空白與換行差異(data, fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["quote"] = "Prescription proton pump   inhibitor (PPI)\ndrugs, such as esomeprazole magnesium"
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert check_integrity(data, rules) == []


def test_出處文件不存在也算違規(data, fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["document"] = "sources/nih_ods/Nope-HealthProfessional.md"
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert "document_missing" in codes(check_integrity(data, rules))


def test_只引用Consumer版的規則不合格(data, fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["document"] = "sources/nih_ods/Magnesium-Consumer.md"
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert "consumer_source" in codes(check_integrity(data, rules))


def test_DRIs不能當規則出處類型的替身(data, fixture_rules):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium")
    bad["citations"][0]["document"] = "sources/dris/DRIs_Full.md"
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert "source_type_mismatch" in codes(check_integrity(data, rules))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("ingredient_code", "no_such_ingredient", "unknown_ingredient"),
        ("condition_code", "no_such_class", "unknown_condition"),
        ("condition_type", "drug_ingredient", "unknown_condition"),  # ppi 是類別不是有效成分
    ],
)
def test_規則引用的成分與用藥必須存在於目錄(data, fixture_rules, field, value, expected):
    bad = raw_rule(fixture_rules, "fx-ppi-magnesium") | {field: value}
    rules = fixture_rules.model_copy(update={"rules": (type(fixture_rules.rules[0]).model_validate(bad),)})
    assert expected in codes(check_integrity(data, rules))


def test_規則id不得重複(data, fixture_rules):
    first = fixture_rules.rules[0]
    rules = fixture_rules.model_copy(update={"rules": (first, first)})
    assert "duplicate_rule_id" in codes(check_integrity(data, rules))


def test_Ranitidine不在範圍內(data, fixture_rules):
    assert check_integrity(data, data.rules) == []
    assert data.drugs.class_of("ranitidine") is None
    polluted_drugs = data.drugs.model_copy(
        update={
            "ingredients": (
                *data.drugs.ingredients,
                data.drugs.ingredients[0].model_copy(
                    update={"code": "ranitidine", "name_en": "Ranitidine", "class_code": "ppi"}
                ),
            )
        }
    )
    polluted = data.model_copy(update={"drugs": polluted_drugs})
    assert "ranitidine_in_scope" in codes(check_integrity(polluted, data.rules))
