"""確定性的名稱與單位標準化：查成分目錄與化合物表，不交給 VLM。"""

from typing import Literal, NamedTuple

from nutrition_agent.reference import (
    CompoundCatalog,
    Ingredient,
    IngredientCatalog,
    IngredientCategory,
)
from nutrition_agent.reference.ingredients import normalize_name

ScopeStatus = Literal["in_scope", "out_of_scope", "unconfirmed"]
# 含量依據：labeled = 標示載明的成分含量；compound = 化合物重量（元素量由系統推估）
AmountBasis = Literal["labeled", "compound"]

_UNIT_ALIASES = {
    "mg": "mg", "毫克": "mg", "mcg": "ug", "ug": "ug", "μg": "ug", "µg": "ug", "微克": "ug",
    "g": "g", "公克": "g", "克": "g", "iu": "IU", "i.u.": "IU", "國際單位": "IU",
    "mg_alpha_te": "mg_alpha_te", "mg_ate": "mg_alpha_te", "mgα-te": "mg_alpha_te",
    "mga-te": "mg_alpha_te", "毫克α-te": "mg_alpha_te", "mg_ne": "mg_ne", "mgne": "mg_ne",
    "毫克ne": "mg_ne", "ug_dfe": "ug_dfe", "ugdfe": "ug_dfe", "μgdfe": "ug_dfe",
    "微克dfe": "ug_dfe", "kcal": "kcal", "大卡": "kcal",
}  # fmt: skip
DOSE_UNITS = ("粒", "錠", "包", "匙", "毫升")
# 營養標示的固定欄位：不是成分，校對頁不顯示（#22）。只比對完整名稱，「乳糖」「硫酸月桂酯鈉」不算
_NUTRITION_FACTS = {
    "熱量", "能量", "蛋白質", "脂肪", "總脂肪", "飽和脂肪", "飽和脂肪酸", "反式脂肪", "反式脂肪酸",
    "碳水化合物", "總碳水化合物", "糖", "總糖", "糖類", "添加糖", "鈉", "膳食纖維",
    "calories", "energy", "protein", "fat", "totalfat", "saturatedfat", "transfat",
    "carbohydrate", "carbohydrates", "totalcarbohydrate", "sugar", "sugars", "sodium", "dietaryfiber",
}  # fmt: skip
_OPEN, _CLOSE = "(（", ")）"


def normalize_unit(unit: str | None) -> str | None:
    if not unit or not unit.strip():
        return None
    key = "".join(unit.split()).casefold().replace("(", "").replace(")", "")
    return _UNIT_ALIASES.get(key, unit.strip())


def normalize_dose_unit(unit: str | None) -> str | None:
    return unit if unit in DOSE_UNITS else None


def _split_top_level(raw_name: str) -> tuple[str, list[str]]:
    """拆出最外層括號：(括號外的文字, [各組最外層括號的內容])。內層括號屬於括號裡那個成分，不單獨查表。"""
    outside, groups, current, depth = [], [], [], 0
    for ch in raw_name:
        if ch in _OPEN:
            if depth:
                current.append(ch)
            depth += 1
        elif ch in _CLOSE and depth:
            depth -= 1
            if depth:
                current.append(ch)
            else:
                groups.append("".join(current))
                current = []
        elif depth:
            current.append(ch)
        else:
            outside.append(ch)
    return "".join(outside).strip(), groups


def _name_candidates(raw_name: str) -> list[str]:
    without_parens, inner = _split_top_level(raw_name)
    return [raw_name, without_parens, *inner]


def is_nutrition_fact(raw_name: str) -> bool:
    without_parens, _ = _split_top_level(raw_name)
    return normalize_name(without_parens) in _NUTRITION_FACTS


class NameMatch(NamedTuple):
    ingredient_code: str | None  # None = 查不到
    scope_status: ScopeStatus
    basis: AmountBasis = "labeled"
    compound_code: str | None = None  # basis 為 compound 時的化合物


def _scope(ingredient: Ingredient | None) -> ScopeStatus:
    in_scope = ingredient is not None and ingredient.category is not IngredientCategory.OUT_OF_SCOPE
    return "in_scope" if in_scope else "out_of_scope"


def classify(raw_name: str, catalog: IngredientCatalog, compounds: CompoundCatalog) -> NameMatch:
    """同義詞查表：候選名稱依序（全名、括號外、各組最外層括號內）比對，每個候選先查成分目錄、再查化合物表。

    比對到化合物時回傳它所屬的目標營養素與化合物代碼，含量依據為化合物重量；
    「鈣（碳酸鈣）」會先在括號外比到「鈣」，維持標示載明。都查不到 = 無法確認。
    """
    for candidate in _name_candidates(raw_name):
        if not normalize_name(candidate):
            continue
        if (found := catalog.find(candidate)) is not None:
            return NameMatch(found.code, _scope(found))
        if (compound := compounds.find(candidate)) is not None:
            nutrient = compound.nutrient_code
            return NameMatch(nutrient, _scope(catalog.get(nutrient)), "compound", compound.code)
    return NameMatch(None, "unconfirmed")
