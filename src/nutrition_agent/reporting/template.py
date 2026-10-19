"""報告模板：判定 → 分段的純文字報告。

數值、百分比、揭露事項全部在這裡由模板渲染，不經過 LLM。
報告永遠不寫「安全」「未發現問題」，也不給劑量建議。
後續的票在 `render_report` 加新段落（交互作用、完整揭露）；每段是 `Section(key, title, lines)`。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nutrition_agent.accounts import NO_CONDITION
from nutrition_agent.assessment import (
    ANTACID_REMINDER,
    HEALTHY_POPULATION,
    MEDICATION_SOURCE_EXCLUDED,
    PREGNANCY_LACTATION,
    SAME_DAY_ASSUMPTION,
    SCOPE_COVERAGE,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    InteractionFinding,
    Medication,
    IngredientLine,
    Product,
    UlComparison,
)
from nutrition_agent.reference import IngredientCategory, ReferenceData
from nutrition_agent.reporting.explanation import FindingExplanation, Footnote

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

ESTIMATE_NOTE = "此數值為系統推估，非標示值"

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
    SAME_DAY_ASSUMPTION: (
        "你有非每天服用的產品；跨產品加總假設所有產品在同一天服用，"
        "實際服用日不同時，加總會高估。"
    ),
    MEDICATION_SOURCE_EXCLUDED: (
        "鈣、鎂、鐵的攝取量沒有計入藥品來源（例如含鈣或含鎂的制酸劑、軟便劑），"
        "只計算你填寫的保健食品。"
    ),
    ANTACID_REMINDER: (
        "特別提醒：你的用藥中有含鈣或含鎂的制酸劑，它的鈣、鎂不在上述攝取量內，"
        "實際攝取量可能比報告上的數字更高，建議諮詢藥師。"
    ),
    PREGNANCY_LACTATION: "本系統不評估孕期和哺乳期。",
}
UNCOVERED_DRUGS = (
    "DPP-4 抑制劑",
    "磺醯脲類",
    "傳統 NSAIDs",
    "抗凝血與抗血小板藥",
    "骨鬆用藥",
)
CONSULT_TEXT = "若有以上藥物，或有其他本系統未涵蓋的疾病、用藥與身體狀況，請諮詢醫師、藥師或營養師。"


class CardValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    text: str


class Card(BaseModel):
    """交互作用卡片的結構化內容（前端渲染成卡片）；`lines` 仍保留同樣的純文字。"""

    model_config = ConfigDict(frozen=True)

    ingredient: str
    ingredient_code: str
    drugs: list[str]
    reasons: list[str]
    advice: list[str]
    values: list[CardValue]


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    lines: list[str]
    cards: list[Card] = []


class Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    sections: list[Section]
    # 白話解釋與腳註在送出時產生（reporting/explanation.py），整份凍結在報告裡。
    explanations: list[FindingExplanation] = []
    footnotes: list[Footnote] = []


def render_report(
    case: AssessmentCase,
    assessment: Assessment,
    ref: ReferenceData,
    explanations: list[FindingExplanation] | None = None,
    footnotes: list[Footnote] | None = None,
) -> Report:
    names = _Names(ref)
    return Report(
        explanations=explanations or [],
        footnotes=footnotes or [],
        sections=[
            Section(key="profile", title="你的資料", lines=_profile_lines(case, names, ref)),
            Section(
                key="interaction",
                title="交互作用",
                lines=_interaction_lines(case, assessment, names),
                cards=[_card(f, names) for f in assessment.interactions],
            ),
            Section(
                key="ul_comparison",
                title="上限比對",
                lines=_ul_lines(assessment, ref, names),
            ),
            Section(
                key="scope",
                title="評估範圍與揭露",
                lines=_scope_lines(assessment, names, ref),
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
    # 上限比對一律用服用當日的峰值；非每日服用時，措辭明講是「服用當日」，平均只當參考。
    if c.non_daily:
        head = (
            f"{names(c.nutrient_code)}：服用當日來自補充劑的攝取量 {_num(c.intake)} {c.unit}"
            f"（平均每日 {_num(c.average_intake)} {c.unit}）"
        )
    else:
        head = f"{names(c.nutrient_code)}：來自補充劑的每日攝取量 {_num(c.intake)} {c.unit}"
    if c.ul is None:
        note = f"（{ESTIMATE_NOTE}）" if c.estimated else ""
        return f"{head}；無已知上限攝取量{note}"
    scope = "上限只計算補充劑來源" if c.supplement_only else "上限定義上包含飲食"
    flag = "，已超過上限" if c.exceeded else ""
    note = f"；{ESTIMATE_NOTE}" if c.estimated else ""
    if c.non_daily:
        return (
            f"{head}；你服用當日來自補充劑的攝取量已達上限的 "
            f"{_num(c.ul_percent)}%{flag}（上限 {_num(c.ul)} {c.unit}；{scope}）{note}"
        )
    return f"{head}；佔上限 {_num(c.ul)} {c.unit} 的 {_num(c.ul_percent)}%{flag}（{scope}）{note}"


def _interaction_lines(
    case: AssessmentCase, assessment: Assessment, names: _Names
) -> list[str]:
    if assessment.interactions:
        return [line for f in assessment.interactions for line in _card_lines(f, names)]
    if not case.medications:
        return [NO_MEDICATION_INTERACTION_TEXT]
    return [NO_HIT_TEXT if assessment.approved_rule_count else NO_RULES_TEXT]


def _card(f: InteractionFinding, names: _Names) -> Card:
    return Card(
        ingredient=names(f.ingredient_code),
        ingredient_code=f.ingredient_code,
        drugs=[d.raw_name for d in f.triggering_drugs],
        reasons=list(f.reasons_zh),
        advice=[_advice_text(f, a) for a in f.advice],
        values=_card_values(f),
    )


def _card_lines(f: InteractionFinding, names: _Names) -> list[str]:
    card = _card(f, names)
    drugs = " 與 ".join(card.drugs)
    lines = [f"{card.ingredient}：因為你正在服用 {drugs}", *card.reasons]
    lines.append("建議行動：" + "；".join(card.advice))
    if card.values:
        lines.append("參考數值：" + "；".join(f"{v.label} {v.text}" for v in card.values))
    return lines


def _advice_text(f: InteractionFinding, advice: str) -> str:
    if advice == "separate_timing":
        return f"與藥物錯開服用，至少相隔 {f.separation_hours} 小時"
    return ADVICE_TEXT[advice]


def _card_values(f: InteractionFinding) -> list[CardValue]:
    """三個數值並列，不判斷高低、不說不足。允許成分（無 DRIs）沒有數值。"""
    if f.unit is None:
        return []
    intake = (
        f"{_num(f.supplement_intake)} {f.unit}" if f.supplement_intake is not None else "無法判定"
    )
    total = (
        f"{_num(f.recommended_total.value)} {f.recommended_total.unit}"
        f"（{f.recommended_total.kind}）"
        if f.recommended_total
        else "無"
    )
    ul = f"{_num(f.ul)} {f.unit}" if f.ul is not None else "無已知上限攝取量"
    return [
        CardValue(label="來自補充劑", text=intake),
        CardValue(label="建議總攝取量（含飲食）", text=total),
        CardValue(label="上限", text=ul),
    ]


def _scope_lines(assessment: Assessment, names: _Names, ref: ReferenceData) -> list[str]:
    lines = [
        f"{i.product_name} 含「{names(i.ingredient_code)}」：不在本系統評估範圍，已如實保留"
        for i in assessment.out_of_scope_ingredients
    ]
    lines.extend(
        f"注意：{i.product_name} 有無法確認的成分：系統無法確認它是什麼，"
        "可能是範圍內成分的其他寫法，建議諮詢藥師"
        for i in assessment.unconfirmed_ingredients
    )
    for code in assessment.disclosures:
        if code == SCOPE_COVERAGE:
            lines.extend(_coverage_lines(ref))
        else:
            lines.append(DISCLOSURE_TEXT[code])
    return lines


def _coverage_lines(ref: ReferenceData) -> list[str]:
    conditions = list(CONDITION_LABELS.values())
    classes = [c.name_zh for c in ref.drugs.classes]
    nutrients = [i.display_name_zh for i in ref.ingredients.by_category(IngredientCategory.TARGET_NUTRIENT)]
    return [
        f"本系統涵蓋 {len(conditions)} 種慢性病：{'、'.join(conditions)}",
        f"本系統涵蓋 {len(classes)} 類用藥：{'、'.join(classes)}",
        f"本系統涵蓋 {len(nutrients)} 項營養素：{'、'.join(nutrients)}",
        f"台灣常見但本系統未涵蓋的藥：{'、'.join(UNCOVERED_DRUGS)}",
        CONSULT_TEXT,
    ]
