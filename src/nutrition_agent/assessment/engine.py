"""判定引擎：評估個案快照＋參考資料 → 判定。純函數，不碰資料庫與模型。"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from nutrition_agent.accounts import NO_CONDITION
from nutrition_agent.assessment.models import (
    HEALTHY_POPULATION,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    IngredientLine,
    ListedIngredient,
    NutrientSource,
    Product,
    UlComparison,
)
from nutrition_agent.reference import (
    DriKind,
    IngredientCategory,
    ReferenceData,
    Sex,
    UlScope,
    UnitNotConvertible,
)


def _exact(value: float) -> Fraction:
    """用十進位字面值轉成精確分數，避免 0.1 這類浮點誤差影響 ≥100% 的判斷。"""
    return Fraction(str(value))


def daily_servings(product: Product) -> Fraction:
    """每日份數 ＝ 每日劑型單位數 ÷ 每份劑型單位數。"""
    daily_units = product.intake.times_per_day * _exact(product.intake.units_per_time)
    return daily_units / _exact(product.units_per_serving)


def assess(case: AssessmentCase, ref: ReferenceData) -> Assessment:
    sex = Sex(case.profile.sex)
    totals: dict[str, Fraction] = {}
    estimated_codes: set[str] = set()
    undetermined: set[str] = set()
    sources: list[NutrientSource] = []
    out_of_scope: list[ListedIngredient] = []
    unconfirmed: list[ListedIngredient] = []

    for product in case.products:
        servings = daily_servings(product)
        target_lines: dict[str, list[IngredientLine]] = {}
        for item in product.ingredients:
            code = item.ingredient_code
            listed = ListedIngredient(product_name=product.name, ingredient_code=code)
            ingredient = None if code == UNKNOWN_INGREDIENT else ref.ingredients.get(code)
            if ingredient is None:
                unconfirmed.append(listed)
            elif ingredient.category is IngredientCategory.OUT_OF_SCOPE:
                out_of_scope.append(listed)
            elif ingredient.category is IngredientCategory.TARGET_NUTRIENT:
                target_lines.setdefault(code, []).append(item)
        for code, lines in target_lines.items():
            ul = ref.dris.lookup(code, DriKind.UL, age=case.age, sex=sex)
            target_unit = ul.unit if ul else ref.ingredients.get(code).canonical_unit
            source = _resolve_nutrient(product.name, code, lines, target_unit, ref)
            sources.append(source.record)
            if source.amount is None:
                undetermined.add(code)
                continue
            totals[code] = totals.get(code, Fraction(0)) + source.amount * servings
            if source.record.source == "estimated":
                estimated_codes.add(code)

    comparisons = [
        _compare(code, intake, case, ref, sex, code in estimated_codes)
        for code, intake in sorted(totals.items(), key=lambda kv: _order(ref, kv[0]))
        if code not in undetermined
    ]
    return Assessment(
        reference_version=ref.version,
        ul_comparisons=comparisons,
        out_of_scope_ingredients=out_of_scope,
        unconfirmed_ingredients=unconfirmed,
        undetermined_nutrients=sorted(undetermined),
        nutrient_sources=sources,
        disclosures=_disclosures(case),
    )


@dataclass(frozen=True)
class _Resolved:
    record: NutrientSource
    amount: Fraction | None  # 每份、DRIs 單位的元素量；None = 無法判定


def _resolve_nutrient(
    product_name: str, code: str, lines: list[IngredientLine], target_unit: str, ref: ReferenceData
) -> _Resolved:
    """一項產品裡同一營養素的元素量：標示載明 > 推估 > 無法判定。"""

    def result(kind: str, amount: Fraction | None, compound: str | None = None) -> _Resolved:
        record = NutrientSource(
            product_name=product_name, nutrient_code=code, source=kind, compound_code=compound
        )
        return _Resolved(record, amount)

    labeled = [_labeled_amount(code, i, target_unit, ref) for i in lines if i.basis == "labeled"]
    if labeled and all(a is not None for a in labeled):
        return result("labeled", sum(labeled, Fraction(0)))
    estimates = [_estimated_amount(code, i, target_unit, ref) for i in lines]
    if not estimates or any(a is None for a in estimates):
        return result("undetermined", None)
    compounds = sorted({i.compound_code for i in lines if i.compound_code})
    return result("estimated", sum(estimates, Fraction(0)), compounds[0])


def _labeled_amount(
    code: str, item: IngredientLine, target_unit: str, ref: ReferenceData
) -> Fraction | None:
    try:
        return _exact(ref.units.convert(code, item.amount, item.unit, target_unit))
    except UnitNotConvertible:
        return None


def _estimated_amount(
    code: str, item: IngredientLine, target_unit: str, ref: ReferenceData
) -> Fraction | None:
    """標示載明的行直接換算；化合物行用元素比率推估，表內查不到或營養素不符 → None。"""
    if item.basis == "labeled":
        return _labeled_amount(code, item, target_unit, ref)
    compound = ref.compounds.get(item.compound_code) if item.compound_code else None
    if compound is None or compound.nutrient_code != code:
        return None
    try:
        weight_mg = ref.units.convert(code, item.amount, item.unit, "mg")
        element_mg = _exact(weight_mg) * _exact(compound.element_ratio)
        return _exact(ref.units.convert(code, float(element_mg), "mg", target_unit))
    except UnitNotConvertible:
        return None


def _disclosures(case: AssessmentCase) -> list[str]:
    """揭露事項代碼；報告模板負責把代碼渲染成文字。"""
    found = []
    if any(c != NO_CONDITION for c in case.profile.conditions):
        found.append(HEALTHY_POPULATION)
    return found


def _order(ref: ReferenceData, code: str) -> int:
    return ref.ingredients.get(code).sort_order


def _compare(
    code: str,
    intake: Fraction,
    case: AssessmentCase,
    ref: ReferenceData,
    sex: Sex,
    estimated: bool,
) -> UlComparison:
    ul = ref.dris.lookup(code, DriKind.UL, age=case.age, sex=sex)
    unit = ul.unit if ul else ref.ingredients.get(code).canonical_unit
    has_ul = ul is not None and ul.value is not None
    ul_value = _exact(ul.value) if has_ul else None
    return UlComparison(
        nutrient_code=code,
        intake=float(intake),
        unit=unit,
        ul=ul.value if has_ul else None,
        ul_percent=float(intake / ul_value * 100) if ul_value else None,
        exceeded=bool(ul_value and intake >= ul_value),
        supplement_only=bool(ul and ul.ul_scope is UlScope.SUPPLEMENT_ONLY),
        estimated=estimated,
    )
