"""判定引擎：評估個案快照＋參考資料 → 判定。純函數，不碰資料庫與模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from nutrition_agent.accounts import NO_CONDITION
from nutrition_agent.assessment.interactions import find_interactions
from nutrition_agent.assessment.models import (
    ANTACID_REMINDER,
    HEALTHY_POPULATION,
    MEDICATION_SOURCE_EXCLUDED,
    PREGNANCY_LACTATION,
    SAME_DAY_ASSUMPTION,
    SCOPE_COVERAGE,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    Frequency,
    IngredientLine,
    Intake,
    ListedIngredient,
    NutrientSource,
    Product,
    SourceKind,
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


def taking_day_fraction(intake: Intake) -> Fraction:
    """服用日佔全部日子的比例，用來由峰值算平均。"""
    if intake.frequency is Frequency.EVERY_OTHER_DAY:
        return Fraction(1, 2)
    if intake.frequency is Frequency.WEEKLY_DAYS:
        return Fraction(intake.days_per_week, 7)
    if intake.frequency is Frequency.CYCLE:
        return Fraction(intake.cycle_on_days, intake.cycle_on_days + intake.cycle_off_days)
    return Fraction(1)


def daily_servings(product: Product) -> Fraction:
    """服用當日份數（峰值）＝ 當日劑型單位數 ÷ 每份劑型單位數。"""
    daily_units = product.intake.times_per_day * _exact(product.intake.units_per_time)
    return daily_units / _exact(product.units_per_serving)


@dataclass
class _Tally:
    """跨產品累計的中間結果。"""

    totals: dict[str, Fraction] = field(default_factory=dict)  # 峰值加總
    averages: dict[str, Fraction] = field(default_factory=dict)
    non_daily: set[str] = field(default_factory=set)
    estimated_codes: set[str] = field(default_factory=set)
    undetermined: set[str] = field(default_factory=set)
    sources: list[NutrientSource] = field(default_factory=list)
    out_of_scope: list[ListedIngredient] = field(default_factory=list)
    unconfirmed: list[ListedIngredient] = field(default_factory=list)


def _classify_ingredients(
    product: Product, ref: ReferenceData, tally: _Tally
) -> dict[str, list[IngredientLine]]:
    """把產品的成分行分流：範圍外與無法確認的記入揭露清單，目標營養素按代碼回傳。"""
    target_lines: dict[str, list[IngredientLine]] = {}
    for item in product.ingredients:
        code = item.ingredient_code
        listed = ListedIngredient(product_name=product.name, ingredient_code=code)
        ingredient = None if code == UNKNOWN_INGREDIENT else ref.ingredients.get(code)
        if ingredient is None:
            tally.unconfirmed.append(listed)
        elif ingredient.category is IngredientCategory.OUT_OF_SCOPE:
            tally.out_of_scope.append(listed)
        elif ingredient.category is IngredientCategory.TARGET_NUTRIENT:
            target_lines.setdefault(code, []).append(item)
    return target_lines


def _accumulate_product(
    product: Product, case: AssessmentCase, ref: ReferenceData, sex: Sex, tally: _Tally
) -> None:
    servings = daily_servings(product)
    for code, lines in _classify_ingredients(product, ref, tally).items():
        ul = ref.dris.lookup(code, DriKind.UL, age=case.age, sex=sex)
        target_unit = ul.unit if ul else ref.ingredients.get(code).canonical_unit
        source = _resolve_nutrient(product.name, code, lines, target_unit, ref)
        tally.sources.append(source.record)
        if source.amount is None:
            tally.undetermined.add(code)
            continue
        peak = source.amount * servings
        tally.totals[code] = tally.totals.get(code, Fraction(0)) + peak
        tally.averages[code] = tally.averages.get(code, Fraction(0)) + (
            peak * taking_day_fraction(product.intake)
        )
        if not product.intake.is_daily:
            tally.non_daily.add(code)
        if source.record.source is SourceKind.ESTIMATED:
            tally.estimated_codes.add(code)


def assess(case: AssessmentCase, ref: ReferenceData) -> Assessment:
    sex = Sex(case.profile.sex)
    tally = _Tally()
    for product in case.products:
        _accumulate_product(product, case, ref, sex, tally)
    comparisons = [
        _compare(
            code, intake, tally.averages[code], code in tally.non_daily, case, ref, sex,
            code in tally.estimated_codes,
        )
        for code, intake in sorted(tally.totals.items(), key=lambda kv: _order(ref, kv[0]))
        if code not in tally.undetermined
    ]
    return Assessment(
        reference_version=ref.version,
        ul_comparisons=comparisons,
        out_of_scope_ingredients=tally.out_of_scope,
        unconfirmed_ingredients=tally.unconfirmed,
        undetermined_nutrients=sorted(tally.undetermined),
        nutrient_sources=tally.sources,
        disclosures=_disclosures(case),
        interactions=find_interactions(case, ref, comparisons, tally.undetermined),
        approved_rule_count=len(ref.rules.approved()),
    )


@dataclass(frozen=True)
class _Resolved:
    record: NutrientSource
    amount: Fraction | None  # 每份、DRIs 單位的元素量；None = 無法判定


def _resolve_nutrient(
    product_name: str, code: str, lines: list[IngredientLine], target_unit: str, ref: ReferenceData
) -> _Resolved:
    """一項產品裡同一營養素的元素量：標示載明 > 推估 > 無法判定。"""

    def result(kind: SourceKind, amount: Fraction | None, compound: str | None = None) -> _Resolved:
        record = NutrientSource(
            product_name=product_name, nutrient_code=code, source=kind, compound_code=compound
        )
        return _Resolved(record, amount)

    labeled = [_labeled_amount(code, i, target_unit, ref) for i in lines if i.is_user_provided]
    if labeled and all(a is not None for a in labeled):
        return result(SourceKind.LABELED, sum(labeled, Fraction(0)))
    estimates = [_estimated_amount(code, i, target_unit, ref) for i in lines]
    if not estimates or any(a is None for a in estimates):
        return result(SourceKind.UNDETERMINED, None)
    compounds = sorted({i.compound_code for i in lines if i.compound_code})
    return result(SourceKind.ESTIMATED, sum(estimates, Fraction(0)), compounds[0])


def _labeled_amount(
    code: str, item: IngredientLine, target_unit: str, ref: ReferenceData
) -> Fraction | None:
    amount, unit = (
        (item.element_override_mg, "mg") if item.element_override_mg is not None
        else (item.amount, item.unit)
    )
    try:
        return _exact(ref.units.convert(code, amount, unit, target_unit))
    except UnitNotConvertible:
        return None


def _estimated_amount(
    code: str, item: IngredientLine, target_unit: str, ref: ReferenceData
) -> Fraction | None:
    """標示載明的行直接換算；化合物行用元素比率推估，表內查不到或營養素不符 → None。"""
    if item.is_user_provided:
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


ANTACID_CLASS = "calcium_magnesium_antacid"


def _disclosures(case: AssessmentCase) -> list[str]:
    """揭露事項代碼（固定順序）；報告模板負責把代碼渲染成文字。"""
    found = []
    if any(c != NO_CONDITION for c in case.profile.conditions):
        found.append(HEALTHY_POPULATION)
    if any(not p.intake.is_daily for p in case.products):
        found.append(SAME_DAY_ASSUMPTION)
    found.append(MEDICATION_SOURCE_EXCLUDED)
    if any(
        m.scope_status == "in_scope" and any(i.class_code == ANTACID_CLASS for i in m.ingredients)
        for m in case.medications
    ):
        found.append(ANTACID_REMINDER)
    found.extend([PREGNANCY_LACTATION, SCOPE_COVERAGE])
    return found


def _order(ref: ReferenceData, code: str) -> int:
    return ref.ingredients.get(code).sort_order


def _compare(
    code: str,
    intake: Fraction,
    average: Fraction,
    non_daily: bool,
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
        average_intake=float(average),
        non_daily=non_daily,
        unit=unit,
        ul=ul.value if has_ul else None,
        ul_percent=float(intake / ul_value * 100) if ul_value else None,
        exceeded=bool(ul_value and intake >= ul_value),
        supplement_only=bool(ul and ul.ul_scope is UlScope.SUPPLEMENT_ONLY),
        estimated=estimated,
    )
