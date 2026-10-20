"""確定性的名稱與單位標準化：查成分目錄，不交給 VLM。"""

from typing import Literal

from nutrition_agent.reference import IngredientCatalog, IngredientCategory
from nutrition_agent.reference.ingredients import normalize_name

ScopeStatus = Literal["in_scope", "out_of_scope", "unconfirmed"]

_UNIT_ALIASES = {
    "mg": "mg", "毫克": "mg", "mcg": "ug", "ug": "ug", "μg": "ug", "µg": "ug", "微克": "ug",
    "g": "g", "公克": "g", "克": "g", "iu": "IU", "i.u.": "IU", "國際單位": "IU",
    "mg_alpha_te": "mg_alpha_te", "mg_ate": "mg_alpha_te", "mgα-te": "mg_alpha_te",
    "mga-te": "mg_alpha_te", "毫克α-te": "mg_alpha_te", "mg_ne": "mg_ne", "mgne": "mg_ne",
    "毫克ne": "mg_ne", "ug_dfe": "ug_dfe", "ugdfe": "ug_dfe", "μgdfe": "ug_dfe",
    "微克dfe": "ug_dfe", "kcal": "kcal", "大卡": "kcal",
}  # fmt: skip
DOSE_UNITS = ("粒", "錠", "包", "匙", "毫升")
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


def classify(raw_name: str, catalog: IngredientCatalog) -> tuple[str | None, ScopeStatus]:
    """同義詞查表：回傳 (成分代碼, 範圍狀態)；查不到 = (None, 無法確認)。"""
    for candidate in _name_candidates(raw_name):
        if not normalize_name(candidate):
            continue
        found = catalog.find(candidate)
        if found is None:
            continue
        in_scope = found.category is not IngredientCategory.OUT_OF_SCOPE
        return found.code, "in_scope" if in_scope else "out_of_scope"
    return None, "unconfirmed"
