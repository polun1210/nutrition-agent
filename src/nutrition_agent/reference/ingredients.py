"""成分目錄：目標營養素、允許成分、常見範圍外成分。"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class IngredientCategory(StrEnum):
    TARGET_NUTRIENT = "target_nutrient"
    ALLOWED_INGREDIENT = "allowed_ingredient"
    OUT_OF_SCOPE = "out_of_scope"


class Ingredient(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    category: IngredientCategory
    display_name_zh: str
    synonyms: tuple[str, ...] = ()
    sort_order: int
    canonical_unit: str | None = None

    @model_validator(mode="after")
    def _only_targets_have_unit(self) -> Self:
        is_target = self.category is IngredientCategory.TARGET_NUTRIENT
        if is_target != (self.canonical_unit is not None):
            raise ValueError(f"{self.code}: 只有目標營養素要有 canonical_unit")
        return self


def normalize_name(name: str) -> str:
    """名稱比對用：NFKC 正規化、去空白、忽略大小寫。"""
    return "".join(unicodedata.normalize("NFKC", name).split()).casefold()


class IngredientCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    ingredients: tuple[Ingredient, ...]

    @model_validator(mode="after")
    def _unique_codes_and_names(self) -> Self:
        seen_codes: set[str] = set()
        seen_names: dict[str, str] = {}
        for ing in self.ingredients:
            if ing.code in seen_codes:
                raise ValueError(f"成分代碼重複：{ing.code}")
            seen_codes.add(ing.code)
            for name in (ing.display_name_zh, *ing.synonyms):
                key = normalize_name(name)
                if seen_names.setdefault(key, ing.code) != ing.code:
                    raise ValueError(f"名稱 {name!r} 同時屬於 {seen_names[key]} 與 {ing.code}")
        return self

    def get(self, code: str) -> Ingredient | None:
        return next((i for i in self.ingredients if i.code == code), None)

    def codes(self) -> frozenset[str]:
        return frozenset(i.code for i in self.ingredients)

    def by_category(self, category: IngredientCategory) -> tuple[Ingredient, ...]:
        found = (i for i in self.ingredients if i.category is category)
        return tuple(sorted(found, key=lambda i: i.sort_order))

    def find(self, name: str) -> Ingredient | None:
        """以顯示名稱或同義詞找標準成分；找不到回傳 None。"""
        key = normalize_name(name)
        for ing in self.ingredients:
            if key in {normalize_name(n) for n in (ing.display_name_zh, *ing.synonyms)}:
                return ing
        return None
