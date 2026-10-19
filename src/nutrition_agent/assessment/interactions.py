"""交互作用判定：範圍內的用藥 × 範圍內的成分 → 審定規則 → 依成分聚合。

只讀審定規則（`RuleSet.approved()`）。沒有嚴重度；建議行動是封閉的三種。
"""

from __future__ import annotations

from nutrition_agent.assessment.models import (
    AssessmentCase,
    InteractionFinding,
    RecommendedTotal,
    TriggeringDrug,
    UlComparison,
)
from nutrition_agent.reference import (
    Advice,
    ConditionType,
    DriKind,
    IngredientCategory,
    ReferenceData,
    Rule,
    Sex,
)

_ADVICE_ORDER = list(Advice)
_IN_SCOPE_CATEGORIES = (IngredientCategory.TARGET_NUTRIENT, IngredientCategory.ALLOWED_INGREDIENT)


def find_interactions(
    case: AssessmentCase,
    ref: ReferenceData,
    comparisons: list[UlComparison],
    undetermined: set[str],
) -> list[InteractionFinding]:
    matched: dict[str, list[tuple[Rule, list[TriggeringDrug]]]] = {}
    for rule in ref.rules.approved():
        if not _ingredient_in_scope(rule.ingredient_code, ref):
            continue
        if rule.requires_supplement_intake and not _is_supplemented(case, rule):
            continue
        drugs = _triggering_drugs(case, rule)
        if drugs:
            matched.setdefault(rule.ingredient_code, []).append((rule, drugs))

    return [
        _finding(code, hits, case, ref, comparisons, undetermined)
        for code, hits in sorted(matched.items(), key=lambda kv: _order(ref, kv[0]))
    ]


def _order(ref: ReferenceData, code: str) -> int:
    return ref.ingredients.get(code).sort_order


def _ingredient_in_scope(code: str, ref: ReferenceData) -> bool:
    ingredient = ref.ingredients.get(code)
    return ingredient is not None and ingredient.category in _IN_SCOPE_CATEGORIES


def _is_supplemented(case: AssessmentCase, rule: Rule) -> bool:
    return any(
        item.ingredient_code == rule.ingredient_code
        and (rule.ingredient_form is None or item.form == rule.ingredient_form)
        for product in case.products
        for item in product.ingredients
    )


def _triggering_drugs(case: AssessmentCase, rule: Rule) -> list[TriggeringDrug]:
    by_class = rule.condition_type is ConditionType.DRUG_CLASS
    found: list[TriggeringDrug] = []
    for medication in case.medications:
        if medication.scope_status != "in_scope":
            continue
        for item in medication.ingredients:
            if (item.class_code if by_class else item.code) == rule.condition_code:
                found.append(
                    TriggeringDrug(
                        raw_name=medication.raw_name,
                        ingredient_code=item.code,
                        class_code=item.class_code,
                    )
                )
                break
    return found


def _finding(
    code: str,
    hits: list[tuple[Rule, list[TriggeringDrug]]],
    case: AssessmentCase,
    ref: ReferenceData,
    comparisons: list[UlComparison],
    undetermined: set[str],
) -> InteractionFinding:
    rules = sorted((rule for rule, _ in hits), key=lambda r: r.id)
    hit_names = {d.raw_name for _, drugs in hits for d in drugs}
    drugs = [
        next(d for _, ds in hits for d in ds if d.raw_name == m.raw_name)
        for m in case.medications
        if m.raw_name in hit_names
    ]
    advice = {r.advice for r in rules}
    hours = [r.separation_hours for r in rules if r.separation_hours is not None]
    supplemented = any(
        item.ingredient_code == code for p in case.products for item in p.ingredients
    )
    unit, intake, total, ul = _numbers(code, case, ref, comparisons, undetermined)
    return InteractionFinding(
        ingredient_code=code,
        supplemented=supplemented,
        rule_ids=[r.id for r in rules],
        triggering_drugs=drugs,
        reasons_zh=[r.reason_zh for r in rules],
        advice=[a.value for a in _ADVICE_ORDER if a in advice],
        separation_hours=max(hours) if hours else None,
        unit=unit,
        supplement_intake=intake,
        recommended_total=total,
        ul=ul,
    )


def _numbers(
    code: str,
    case: AssessmentCase,
    ref: ReferenceData,
    comparisons: list[UlComparison],
    undetermined: set[str],
) -> tuple[str | None, float | None, RecommendedTotal | None, float | None]:
    """補充劑來源攝取量、建議總攝取量、上限：只並列，不判斷。"""
    if ref.ingredients.get(code).category is not IngredientCategory.TARGET_NUTRIENT:
        return None, None, None, None
    sex = Sex(case.profile.sex)
    ul_entry = ref.dris.lookup(code, DriKind.UL, age=case.age, sex=sex)
    unit = ul_entry.unit if ul_entry else ref.ingredients.get(code).canonical_unit
    comparison = next((c for c in comparisons if c.nutrient_code == code), None)
    intake = None if code in undetermined else (comparison.intake if comparison else 0.0)
    return unit, intake, _recommended(code, case, ref, sex), ul_entry.value if ul_entry else None


def _recommended(
    code: str, case: AssessmentCase, ref: ReferenceData, sex: Sex
) -> RecommendedTotal | None:
    for kind, label in ((DriKind.RDA, "RDA"), (DriKind.AI, "AI")):
        entry = ref.dris.lookup(code, kind, age=case.age, sex=sex)
        if entry is not None and entry.value is not None:
            return RecommendedTotal(value=entry.value, unit=entry.unit, kind=label)
    return None
