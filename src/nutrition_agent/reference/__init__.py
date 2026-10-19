"""參考資料：成分目錄、用藥類別、DRIs、單位換算、交互作用規則。"""

from nutrition_agent.reference.checks import Violation, check_integrity
from nutrition_agent.reference.dris import DriEntry, DriKind, DriTable, Sex, UlScope
from nutrition_agent.reference.drugs import DrugCatalog, DrugClass, DrugIngredient, DrugRole
from nutrition_agent.reference.ingredients import (
    Ingredient,
    IngredientCatalog,
    IngredientCategory,
)
from nutrition_agent.reference.loader import ReferenceData, load_reference_data, load_rule_set
from nutrition_agent.reference.rules import (
    Advice,
    Citation,
    ConditionType,
    InteractionType,
    Rule,
    RuleSet,
    RuleStatus,
    SourceType,
)
from nutrition_agent.reference.units import UnitConversions, UnitNotConvertible, UnitRule

__all__ = [
    "Advice",
    "Citation",
    "ConditionType",
    "DriEntry",
    "DriKind",
    "DriTable",
    "DrugCatalog",
    "DrugClass",
    "DrugIngredient",
    "DrugRole",
    "Ingredient",
    "IngredientCatalog",
    "IngredientCategory",
    "InteractionType",
    "ReferenceData",
    "Rule",
    "RuleSet",
    "RuleStatus",
    "Sex",
    "SourceType",
    "UlScope",
    "UnitConversions",
    "UnitNotConvertible",
    "UnitRule",
    "Violation",
    "check_integrity",
    "load_reference_data",
    "load_rule_set",
]
