"""報告模板：判定 → 分段的純文字報告。

數值、百分比、揭露事項全部在這裡由模板渲染，不經過 LLM。
報告永遠不寫「安全」「未發現問題」，也不給劑量建議。
後續的票在 `render_report` 加新段落（交互作用、完整揭露）；每段是 `Section(key, title, lines)`。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nutrition_agent.accounts import NO_CONDITION
from nutrition_agent.assessment import (
    HEALTHY_POPULATION,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    IngredientLine,
    Product,
    UlComparison,
)
from nutrition_agent.reference import ReferenceData

CONDITION_LABELS = {
    "hypertension": "高血壓",
    "type2_diabetes": "第二型糖尿病",
    "hyperlipidemia": "高血脂",
    "chronic_arthritis": "慢性關節炎",
    "chronic_insomnia": "慢性失眠症",
}
SEX_LABELS = {"male": "男性", "female": "女性"}
UNKNOWN_LABEL = "無法確定"

ESTIMATE_NOTE = "此數值為系統推估，非標示值"

DISCLOSURE_TEXT = {
    HEALTHY_POPULATION: "DRIs 的參考值適用於健康族群；你勾選了慢性病，這些數值僅供對照。",
}


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    lines: list[str]


class Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    sections: list[Section]


def render_report(case: AssessmentCase, assessment: Assessment, ref: ReferenceData) -> Report:
    names = _Names(ref)
    return Report(
        sections=[
            Section(key="profile", title="你的資料", lines=_profile_lines(case, names, ref)),
            Section(
                key="ul_comparison",
                title="上限比對",
                lines=_ul_lines(assessment, ref, names),
            ),
            Section(
                key="scope",
                title="評估範圍與揭露",
                lines=_scope_lines(assessment, names),
            ),
        ]
    )


class _Names:
    """成分代碼 → 顯示名稱。"""

    def __init__(self, ref: ReferenceData) -> None:
        self._ref = ref

    def __call__(self, code: str) -> str:
        if code == UNKNOWN_INGREDIENT:
            return UNKNOWN_LABEL
        ingredient = self._ref.ingredients.get(code)
        return ingredient.display_name_zh if ingredient else code


def _compound_name(ref: ReferenceData, code: str | None) -> str:
    compound = ref.compounds.get(code) if code else None
    return compound.display_name_zh if compound else "未知化合物"


def _num(value: float) -> str:
    return f"{round(value, 1):g}"


def _profile_lines(case: AssessmentCase, names: _Names, ref: ReferenceData) -> list[str]:
    profile = case.profile
    lines = [f"年齡：{case.age} 歲（評估當天）", f"性別：{SEX_LABELS[profile.sex]}"]
    chosen = [CONDITION_LABELS[c] for c in profile.conditions if c != NO_CONDITION]
    lines.append(
        f"你勾選了{'、'.join(chosen)}" if chosen else "你未勾選本系統涵蓋的 5 種慢性病"
    )
    lines.extend(_product_line(p, names, ref) for p in case.products)
    return lines


def _ingredient_text(item: IngredientLine, names: _Names, ref: ReferenceData) -> str:
    amount = f"{_num(item.amount)} {item.unit}"
    if item.basis == "labeled":
        return f"{names(item.ingredient_code)} {amount}"
    compound = _compound_name(ref, item.compound_code) if item.compound_code else "化合物未確定"
    return f"{names(item.ingredient_code)}（標示化合物：{compound}）化合物重量 {amount}"


def _product_line(product: Product, names: _Names, ref: ReferenceData) -> str:
    unit = product.dose_unit
    ingredients = "、".join(_ingredient_text(i, names, ref) for i in product.ingredients)
    return (
        f"{product.name}：每份 {_num(product.units_per_serving)} {unit}（每份含 {ingredients}）；"
        f"每天 {product.intake.times_per_day} 次，每次 {_num(product.intake.units_per_time)} {unit}"
    )


def _ul_lines(assessment: Assessment, ref: ReferenceData, names: _Names) -> list[str]:
    lines = [_comparison_line(c, names) for c in assessment.ul_comparisons]
    lines.extend(
        f"{s.product_name} 的{names(s.nutrient_code)}：依化合物「{_compound_name(ref, s.compound_code)}」"
        f"重量推估元素量（{ESTIMATE_NOTE}）"
        for s in assessment.nutrient_sources
        if s.source == "estimated"
    )
    lines.extend(
        f"{names(code)}：無法判定元素量（標示單位無法換算，或只標化合物而無法推估），"
        "未計入上限比對"
        for code in assessment.undetermined_nutrients
    )
    return lines or ["你的保健食品沒有可進行上限比對的目標營養素"]


def _comparison_line(c: UlComparison, names: _Names) -> str:
    head = f"{names(c.nutrient_code)}：來自補充劑的每日攝取量 {_num(c.intake)} {c.unit}"
    if c.ul is None:
        note = f"（{ESTIMATE_NOTE}）" if c.estimated else ""
        return f"{head}；無已知上限攝取量{note}"
    scope = "上限只計算補充劑來源" if c.supplement_only else "上限定義上包含飲食"
    flag = "，已超過上限" if c.exceeded else ""
    note = f"；{ESTIMATE_NOTE}" if c.estimated else ""
    return f"{head}；佔上限 {_num(c.ul)} {c.unit} 的 {_num(c.ul_percent)}%{flag}（{scope}）{note}"


def _scope_lines(assessment: Assessment, names: _Names) -> list[str]:
    lines = [
        f"{i.product_name} 含「{names(i.ingredient_code)}」：不在本系統評估範圍，已如實保留"
        for i in assessment.out_of_scope_ingredients
    ]
    lines.extend(
        f"{i.product_name} 有無法確認的成分：系統無法確認它是什麼，"
        "可能是範圍內成分的其他寫法，建議諮詢藥師"
        for i in assessment.unconfirmed_ingredients
    )
    lines.extend(DISCLOSURE_TEXT[code] for code in assessment.disclosures)
    return lines
