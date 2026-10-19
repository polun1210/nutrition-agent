"""單位換算表：維生素 D 的 IU、維生素 E 的 α-TE、菸鹼素的 NE、葉酸的 DFE 等。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnitNotConvertible(ValueError):
    """換算表裡沒有這組單位的換算途徑。"""


class UnitRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    nutrient_code: str | None = None  # None = 通用
    from_unit: str
    to_unit: str
    factor: float
    source: str


class UnitConversions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    rules: tuple[UnitRule, ...]

    def convert(self, nutrient_code: str, amount: float, from_unit: str, to_unit: str) -> float:
        """換算含量；先找該營養素專屬規則，再找通用規則，正向找不到才取反向倒數。"""
        if from_unit == to_unit:
            return amount
        for scope in (nutrient_code, None):
            for rule in self.rules:
                if rule.nutrient_code != scope:
                    continue
                if (rule.from_unit, rule.to_unit) == (from_unit, to_unit):
                    return amount * rule.factor
                if (rule.to_unit, rule.from_unit) == (from_unit, to_unit):
                    return amount / rule.factor
        raise UnitNotConvertible(f"{nutrient_code}: 沒有 {from_unit} → {to_unit} 的換算規則")
