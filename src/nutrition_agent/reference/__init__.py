"""參考資料：成分目錄、用藥類別、DRIs、單位換算、交互作用規則。"""

from nutrition_agent.reference.drugs import DrugCatalog, DrugClass, DrugIngredient, DrugRole
from nutrition_agent.reference.ingredients import (
    Ingredient,
    IngredientCatalog,
    IngredientCategory,
)
from nutrition_agent.reference.loader import ReferenceData, load_reference_data

__all__ = [
    "DrugCatalog",
    "DrugClass",
    "DrugIngredient",
    "DrugRole",
    "Ingredient",
    "IngredientCatalog",
    "IngredientCategory",
    "ReferenceData",
    "load_reference_data",
]
