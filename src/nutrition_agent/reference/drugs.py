"""用藥類別（規則型／覆蓋型）與其有效成分。"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class DrugRole(StrEnum):
    RULE_BEARING = "rule_bearing"
    COVERAGE_ONLY = "coverage_only"


class DrugClass(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    name_zh: str
    group: str
    role: DrugRole


class DrugIngredient(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    class_code: str
    name_en: str
    name_zh: str


class DrugCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    classes: tuple[DrugClass, ...]
    ingredients: tuple[DrugIngredient, ...]

    @model_validator(mode="after")
    def _unique_and_linked(self) -> Self:
        class_codes = [c.code for c in self.classes]
        if len(set(class_codes)) != len(class_codes):
            raise ValueError("用藥類別代碼重複")
        codes = [i.code for i in self.ingredients]
        if len(set(codes)) != len(codes):
            raise ValueError("有效成分代碼重複")
        unknown = {i.class_code for i in self.ingredients} - set(class_codes)
        if unknown:
            raise ValueError(f"有效成分指向不存在的用藥類別：{sorted(unknown)}")
        return self

    def get_class(self, code: str) -> DrugClass:
        return next(c for c in self.classes if c.code == code)

    def by_role(self, role: DrugRole) -> tuple[DrugClass, ...]:
        return tuple(c for c in self.classes if c.role is role)

    def class_of(self, ingredient_code: str) -> str | None:
        """有效成分所屬的用藥類別代碼；不在範圍內回傳 None。"""
        found = next((i for i in self.ingredients if i.code == ingredient_code), None)
        return found.class_code if found else None
