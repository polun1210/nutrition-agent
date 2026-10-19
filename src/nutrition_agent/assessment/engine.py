"""判定引擎：評估個案快照＋參考資料 → 判定。純函數，不碰資料庫與模型。"""

from __future__ import annotations

from fractions import Fraction

from nutrition_agent.accounts import NO_CONDITION
from nutrition_agent.assessment.interactions import find_interactions
from nutrition_agent.assessment.models import (
    HEALTHY_POPULATION,
    UNKNOWN_INGREDIENT,
    Assessment,
    AssessmentCase,
    Intake,
    ListedIngredient,
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


def taking_day_fraction(intake: Intake) -> Fraction:
    """服用日佔全部日子的比例，用來由峰值算平均。"""
    if intake.frequency == "every_other_day":
        return Fraction(1, 2)
    if intake.frequency == "weekly_days":
        return Fraction(intake.days_per_week, 7)
    if intake.frequency == "cycle":
        return Fraction(intake.cycle_on_days, intake.cycle_on_days + intake.cycle_off_days)
    return Fraction(1)


def daily_servings(product: Product) -> Fraction:
    """服用當日份數（峰值）＝ 當日劑型單位數 ÷ 每份劑型單位數。"""
    daily_units = product.intake.times_per_day * _exact(product.intake.units_per_time)
    return daily_units / _exact(product.units_per_serving)


def assess(case: AssessmentCase, ref: ReferenceData) -> Assessment:
    sex = Sex(case.profile.sex)
    totals: dict[str, Fraction] = {}  # 跨產品的峰值加總
    averages: dict[str, Fraction] = {}
    non_daily: set[str] = set()
    undetermined: set[str] = set()
    out_of_scope: list[ListedIngredient] = []
    unconfirmed: list[ListedIngredient] = []

    for product in case.products:
        servings = daily_servings(product)
        for item in product.ingredients:
            code = item.ingredient_code
            listed = ListedIngredient(product_name=product.name, ingredient_code=code)
            ingredient = None if code == UNKNOWN_INGREDIENT else ref.ingredients.get(code)
            if ingredient is None:
                unconfirmed.append(listed)
            elif ingredient.category is IngredientCategory.OUT_OF_SCOPE:
                out_of_scope.append(listed)
            elif ingredient.category is IngredientCategory.TARGET_NUTRIENT:
                ul = ref.dris.lookup(code, DriKind.UL, age=case.age, sex=sex)
                target_unit = ul.unit if ul else ingredient.canonical_unit
                try:
                    amount = ref.units.convert(code, item.amount, item.unit, target_unit)
                except UnitNotConvertible:
                    undetermined.add(code)
                    continue
                peak = _exact(amount) * servings
                totals[code] = totals.get(code, Fraction(0)) + peak
                averages[code] = (
                    averages.get(code, Fraction(0)) + peak * taking_day_fraction(product.intake)
                )
                if not product.intake.is_daily:
                    non_daily.add(code)

    comparisons = [
        _compare(code, intake, averages[code], code in non_daily, case, ref, sex)
        for code, intake in sorted(totals.items(), key=lambda kv: _order(ref, kv[0]))
        if code not in undetermined
    ]
    return Assessment(
        reference_version=ref.version,
        ul_comparisons=comparisons,
        out_of_scope_ingredients=out_of_scope,
        unconfirmed_ingredients=unconfirmed,
        undetermined_nutrients=sorted(undetermined),
        disclosures=_disclosures(case),
        interactions=find_interactions(case, ref, comparisons, undetermined),
        approved_rule_count=len(ref.rules.approved()),
    )


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
    average: Fraction,
    non_daily: bool,
    case: AssessmentCase,
    ref: ReferenceData,
    sex: Sex,
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
    )
