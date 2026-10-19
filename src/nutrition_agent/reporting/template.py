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
    InteractionFinding,
    Medication,
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
NO_MEDICATION_TEXT = "你沒有提供用藥資料"

NO_RULES_TEXT = (
    "本系統目前尚無已審定的交互作用規則，因此無法比對你的用藥與保健食品；"
    "這不表示兩者不會交互作用，請諮詢藥師或醫師。"
)
NO_HIT_TEXT = (
    "你的用藥與保健食品未命中已審定的規則；本系統只涵蓋部分用藥類別與成分，"
    "這不表示兩者不會交互作用，請諮詢藥師或醫師。"
)
NO_MEDICATION_INTERACTION_TEXT = "你沒有提供用藥資料，未進行交互作用比對。"
ADVICE_TEXT = {
    "inform_provider": "告知你的醫師或藥師",
    "consult_before_combining": "合併使用前先諮詢醫師或藥師",
}

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
            Section(key="profile", title="你的資料", lines=_profile_lines(case, names)),
            Section(
                key="ul_comparison",
                title="上限比對",
                lines=_ul_lines(assessment, names),
            ),
            Section(
                key="interaction",
                title="交互作用",
                lines=_interaction_lines(case, assessment, names),
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


def _num(value: float) -> str:
    return f"{round(value, 1):g}"


def _profile_lines(case: AssessmentCase, names: _Names) -> list[str]:
    profile = case.profile
    lines = [f"年齡：{case.age} 歲（評估當天）", f"性別：{SEX_LABELS[profile.sex]}"]
    chosen = [CONDITION_LABELS[c] for c in profile.conditions if c != NO_CONDITION]
    lines.append(
        f"你勾選了{'、'.join(chosen)}" if chosen else "你未勾選本系統涵蓋的 5 種慢性病"
    )
    lines.extend(_product_line(p, names) for p in case.products)
    lines.extend(_medication_lines(case.medications))
    return lines


def _medication_lines(medications: list[Medication]) -> list[str]:
    if not medications:
        return [NO_MEDICATION_TEXT]
    return [_medication_line(m) for m in medications]


def _medication_line(m: Medication) -> str:
    if m.scope_status == "unconfirmed":
        return f"用藥 {m.raw_name}：無法判斷是否有交互作用（藥名表查不到，可能是寫法不同或已註銷）"
    parts = [f"中文藥名 {m.name_zh}"] if m.name_zh else []
    english = "、".join(i.name_en for i in m.ingredients) or "、".join(m.out_of_scope_names)
    if english:
        parts.append(f"有效成分 {english}")
    detail = f"（{'；'.join(parts)}）" if parts else ""
    if m.scope_status == "out_of_scope":
        return f"用藥 {m.raw_name}：不在本系統評估範圍{detail}"
    return f"用藥 {m.raw_name}：在評估範圍內{detail}"


def _product_line(product: Product, names: _Names) -> str:
    unit = product.dose_unit
    ingredients = "、".join(
        f"{names(i.ingredient_code)} {_num(i.amount)} {i.unit}" for i in product.ingredients
    )
    return (
        f"{product.name}：每份 {_num(product.units_per_serving)} {unit}（每份含 {ingredients}）；"
        f"每天 {product.intake.times_per_day} 次，每次 {_num(product.intake.units_per_time)} {unit}"
    )


def _ul_lines(assessment: Assessment, names: _Names) -> list[str]:
    lines = [_comparison_line(c, names) for c in assessment.ul_comparisons]
    lines.extend(
        f"{names(code)}：標示單位無法換算成 DRIs 的單位，未計入上限比對"
        for code in assessment.undetermined_nutrients
    )
    return lines or ["你的保健食品沒有可進行上限比對的目標營養素"]


def _comparison_line(c: UlComparison, names: _Names) -> str:
    # 上限比對一律用服用當日的峰值；非每日服用時，措辭明講是「服用當日」，平均只當參考。
    if c.non_daily:
        head = (
            f"{names(c.nutrient_code)}：服用當日來自補充劑的攝取量 {_num(c.intake)} {c.unit}"
            f"（平均每日 {_num(c.average_intake)} {c.unit}）"
        )
    else:
        head = f"{names(c.nutrient_code)}：來自補充劑的每日攝取量 {_num(c.intake)} {c.unit}"
    if c.ul is None:
        return f"{head}；無已知上限攝取量"
    scope = "上限只計算補充劑來源" if c.supplement_only else "上限定義上包含飲食"
    flag = "，已超過上限" if c.exceeded else ""
    if c.non_daily:
        return (
            f"{head}；你服用當日來自補充劑的攝取量已達上限的 "
            f"{_num(c.ul_percent)}%{flag}（上限 {_num(c.ul)} {c.unit}；{scope}）"
        )
    return f"{head}；佔上限 {_num(c.ul)} {c.unit} 的 {_num(c.ul_percent)}%{flag}（{scope}）"


def _interaction_lines(
    case: AssessmentCase, assessment: Assessment, names: _Names
) -> list[str]:
    if assessment.interactions:
        return [line for f in assessment.interactions for line in _card_lines(f, names)]
    if not case.medications:
        return [NO_MEDICATION_INTERACTION_TEXT]
    return [NO_HIT_TEXT if assessment.approved_rule_count else NO_RULES_TEXT]


def _card_lines(f: InteractionFinding, names: _Names) -> list[str]:
    drugs = " 與 ".join(d.raw_name for d in f.triggering_drugs)
    lines = [f"{names(f.ingredient_code)}：因為你正在服用 {drugs}", *f.reasons_zh]
    lines.append("建議行動：" + "；".join(_advice_text(f, a) for a in f.advice))
    if f.unit is not None:
        lines.append(_values_line(f))
    return lines


def _advice_text(f: InteractionFinding, advice: str) -> str:
    if advice == "separate_timing":
        return f"與藥物錯開服用，至少相隔 {f.separation_hours} 小時"
    return ADVICE_TEXT[advice]


def _values_line(f: InteractionFinding) -> str:
    """三個數值並列，不判斷高低、不說不足。"""
    intake = (
        f"{_num(f.supplement_intake)} {f.unit}"
        if f.supplement_intake is not None
        else "無法判定"
    )
    total = (
        f"{_num(f.recommended_total.value)} {f.recommended_total.unit}"
        f"（{f.recommended_total.kind}）"
        if f.recommended_total
        else "無"
    )
    ul = f"上限 {_num(f.ul)} {f.unit}" if f.ul is not None else "無已知上限攝取量"
    return f"參考數值：來自補充劑 {intake}；建議總攝取量（含飲食）{total}；{ul}"


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
