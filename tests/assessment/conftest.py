"""判定引擎（Seam B）的合成個案夾具。"""

from pathlib import Path

import pytest

from nutrition_agent.assessment import (
    AssessmentCase,
    IngredientLine,
    Intake,
    Medication,
    MedicationIngredient,
    Product,
    ProfileSnapshot,
)
from nutrition_agent.reference import (
    Citation,
    Rule,
    RuleSet,
    load_reference_data,
    load_rule_set,
)

FIXTURE_RULES = Path(__file__).resolve().parents[1] / "fixtures" / "rules.toml"


@pytest.fixture(scope="session")
def ref():
    return load_reference_data()


@pytest.fixture(scope="session")
def fx_ref(ref):
    """參考資料，但規則換成測試夾具，測試不受真實規則審查結果影響。"""
    return ref.model_copy(update={"rules": load_rule_set(FIXTURE_RULES)})


def with_rules(ref, *rules: Rule):
    return ref.model_copy(update={"rules": RuleSet(version="test", rules=tuple(rules))})


def make_rule(rule_id: str, condition_code: str, ingredient_code: str, **overrides) -> Rule:
    fields = {
        "id": rule_id,
        "condition_type": "drug_ingredient",
        "condition_code": condition_code,
        "ingredient_code": ingredient_code,
        "interaction_type": "drug_affects_nutrient",
        "requires_supplement_intake": False,
        "advice": "inform_provider",
        "reason_zh": f"{rule_id} 的說明文字。",
        "status": "approved",
        "approved_by": "test",
        "citations": [
            Citation(
                source_type="nih_ods_hp",
                document="sources/nih_ods/Calcium-HealthProfessional.md",
                quote="x",
            )
        ],
    }
    return Rule(**{**fields, **overrides})


def drug(raw_name: str, *ingredients: tuple[str, str], scope: str = "in_scope") -> Medication:
    """ingredients: (有效成分代碼, 用藥類別代碼)"""
    return Medication(
        raw_name=raw_name,
        scope_status=scope,
        name_zh=None,
        ingredients=[
            MedicationIngredient(
                code=code, name_en=code, name_zh=code, class_code=cls, class_name_zh=cls
            )
            for code, cls in ingredients
        ],
        out_of_scope_names=[],
    )


def line(code: str, amount: float, unit: str = "mg") -> IngredientLine:
    return IngredientLine(ingredient_code=code, amount=amount, unit=unit)


def product(
    name: str,
    lines: list[IngredientLine],
    *,
    serving: float = 1,
    times_per_day: int = 1,
    per_time: float = 1,
) -> Product:
    return Product(
        name=name,
        dose_unit="粒",
        units_per_serving=serving,
        ingredients=lines,
        intake=Intake(times_per_day=times_per_day, units_per_time=per_time),
    )


def make_case(
    *products: Product,
    sex: str = "female",
    conditions=("none",),
    medications: tuple[Medication, ...] = (),
) -> AssessmentCase:
    return AssessmentCase(
        profile=ProfileSnapshot(
            birth_year=1950, birth_month=6, sex=sex, conditions=list(conditions)
        ),
        age=76,
        assessed_on="2026-10-19",
        products=list(products),
        medications=list(medications),
    )
