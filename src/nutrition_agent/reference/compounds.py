"""化合物比率表：標示只寫化合物重量時，依元素質量比率推估元素量（僅鈣、鎂、鐵）。"""

from __future__ import annotations

import ast
import operator
from typing import Any

from pydantic import BaseModel, ConfigDict

from nutrition_agent.reference.ingredients import normalize_name

# 允許推估的營養素；其他營養素（例如鋅）只標化合物時一律「無法判定」。
SUPPORTED_NUTRIENTS = frozenset({"calcium", "magnesium", "iron"})

_BINARY_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def evaluate_expression(expr: str) -> float:
    """只算四則運算與括號；其他語法一律拒絕（計算式來自資料檔，不執行任意程式）。"""

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
            return _BINARY_OPS[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError(f"計算式只允許數字與 + - * / ( )：{expr!r}")

    try:
        return walk(ast.parse(expr.strip(), mode="eval"))
    except SyntaxError as err:
        raise ValueError(f"計算式語法錯誤：{expr!r}") from err


class Compound(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    nutrient_code: str
    display_name_zh: str
    synonyms: tuple[str, ...] = ()
    formula: str  # 化學式（顯示用）
    molecular_weight_expr: str  # 分子量計算式
    element_mass_expr: str  # 元素質量計算式
    element_ratio: float  # 元素質量 ÷ 分子量


class CompoundCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    compounds: tuple[Compound, ...]

    def get(self, code: str) -> Compound | None:
        return next((c for c in self.compounds if c.code == code), None)

    def find(self, name: str) -> Compound | None:
        key = normalize_name(name)
        for c in self.compounds:
            if key in {normalize_name(n) for n in (c.display_name_zh, *c.synonyms)}:
                return c
        return None
