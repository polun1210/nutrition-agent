"""DRIs 第八版數值：19 歲以上各年齡組與性別的 RDA／AI 與 UL。"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class DriKind(StrEnum):
    RDA = "rda"
    AI = "ai"
    UL = "ul"


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"


class UlScope(StrEnum):
    SUPPLEMENT_ONLY = "supplement_only"  # 鎂、鐵：只計補充劑來源
    INCLUDES_DIET = "includes_diet"  # 其餘：定義上含飲食


class DriEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    nutrient_code: str
    kind: DriKind
    sex: Sex | None  # None = 男女相同
    age_min: int
    age_max: int | None  # None = 無上界
    value: float | None  # UL 為 None = 無已知上限攝取量
    unit: str
    ul_scope: UlScope | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> Self:
        if self.kind is not DriKind.UL and self.value is None:
            raise ValueError(f"{self.nutrient_code}: RDA／AI 必須有數值")
        has_ul_value = self.kind is DriKind.UL and self.value is not None
        if has_ul_value != (self.ul_scope is not None):
            raise ValueError(f"{self.nutrient_code}: 有數值的 UL 才需要（也只有它能有）ul_scope")
        return self

    def covers(self, age: int, sex: Sex) -> bool:
        in_age = age >= self.age_min and (self.age_max is None or age <= self.age_max)
        return in_age and self.sex in (None, sex)


class DriTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    entries: tuple[DriEntry, ...]

    def lookup(self, nutrient_code: str, kind: DriKind, *, age: int, sex: Sex) -> DriEntry | None:
        """查某營養素在指定年齡與性別的數值；沒有該組別的紀錄回傳 None。"""
        for e in self.entries:
            if e.nutrient_code == nutrient_code and e.kind is kind and e.covers(age, sex):
                return e
        return None
