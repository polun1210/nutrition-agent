"""判定引擎：對外只有 `assess(評估個案快照, 參考資料) -> Assessment`。"""

from nutrition_agent.assessment.engine import assess
from nutrition_agent.assessment.models import (
    DOSE_UNITS,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    IngredientLine,
    Intake,
    ListedIngredient,
    Product,
    ProfileSnapshot,
    UlComparison,
)

__all__ = [
    "DOSE_UNITS",
    "UNKNOWN_INGREDIENT",
    "Assessment",
    "AssessmentCase",
    "IngredientLine",
    "Intake",
    "ListedIngredient",
    "Product",
    "ProfileSnapshot",
    "UlComparison",
    "assess",
]
