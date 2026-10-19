"""判定引擎（Seam B）的合成個案夾具。"""

import pytest

from nutrition_agent.assessment import (
    AssessmentCase,
    IngredientLine,
    Intake,
    Product,
    ProfileSnapshot,
)
from nutrition_agent.reference import load_reference_data


@pytest.fixture(scope="session")
def ref():
    return load_reference_data()


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


def make_case(*products: Product, sex: str = "female", conditions=("none",)) -> AssessmentCase:
    return AssessmentCase(
        profile=ProfileSnapshot(
            birth_year=1950, birth_month=6, sex=sex, conditions=list(conditions)
        ),
        age=76,
        assessed_on="2026-10-19",
        products=list(products),
    )
