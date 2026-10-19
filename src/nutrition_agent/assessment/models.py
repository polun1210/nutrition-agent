"""判定引擎的輸入（評估個案快照）與輸出（判定）。

輸入是凍結後的快照，輸出由 `assess` 純函數產生。後續的票（用藥、規則、非每天頻率）
在這些模型上加欄位，不改現有欄位的意思。
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 「無法確定」選單項目的成分代碼：使用者無法判斷標示成分是哪一種時選它。
UNKNOWN_INGREDIENT = "unknown"
# 揭露事項代碼（報告模板依代碼渲染文字）
HEALTHY_POPULATION = "healthy_population"
DOSE_UNITS =("粒", "錠", "包", "匙", "毫升")

PositiveNumber = Annotated[float, Field(gt=0)]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProfileSnapshot(Frozen):
    birth_year: int
    birth_month: int
    sex: Literal["male", "female"]
    conditions: list[str]


class IngredientLine(Frozen):
    ingredient_code: str  # 成分目錄代碼，或 UNKNOWN_INGREDIENT
    amount: Annotated[float, Field(ge=0)]  # 每份含量
    unit: str
    # labeled = amount 是標示載明的元素量；compound = amount 是化合物重量（元素量由系統推估）。
    # 校對頁上使用者覆寫推估值後，這一行就改回 labeled（視為使用者提供的值）。
    basis: Literal["labeled", "compound"] = "labeled"
    compound_code: str | None = None  # basis 為 compound 時的化合物；None = 不在表內


class Intake(Frozen):
    """服用方式：封閉的四種頻率。沒有「需要時才吃」，因為它無法量化。

    times_per_day／units_per_time 描述「服用當日」的劑量（峰值）；頻率決定平均。
    - daily：每天
    - every_other_day：每兩天
    - weekly_days：每週 days_per_week 天（1–6）
    - cycle：服用 cycle_on_days 天、停用 cycle_off_days 天，週期性重複
    """

    frequency: Literal["daily", "every_other_day", "weekly_days", "cycle"] = "daily"
    times_per_day: Annotated[int, Field(ge=1, le=24)]
    units_per_time: PositiveNumber  # 每次幾個劑型單位
    days_per_week: Annotated[int, Field(ge=1, le=6)] | None = None
    cycle_on_days: Annotated[int, Field(ge=1, le=365)] | None = None
    cycle_off_days: Annotated[int, Field(ge=1, le=365)] | None = None

    @model_validator(mode="after")
    def _check_frequency_parameters(self) -> "Intake":
        needed = {
            "weekly_days": {"days_per_week"},
            "cycle": {"cycle_on_days", "cycle_off_days"},
        }.get(self.frequency, set())
        given = {
            name
            for name in ("days_per_week", "cycle_on_days", "cycle_off_days")
            if getattr(self, name) is not None
        }
        if given != needed:
            raise ValueError(f"頻率 {self.frequency} 需要的參數是 {sorted(needed)}")
        return self

    @property
    def is_daily(self) -> bool:
        return self.frequency == "daily"


class Product(Frozen):
    name: Annotated[str, Field(min_length=1)]
    dose_unit: Literal["粒", "錠", "包", "匙", "毫升"]
    units_per_serving: PositiveNumber  # 每份幾個劑型單位
    ingredients: list[IngredientLine]
    intake: Intake


ScopeStatus = Literal["in_scope", "out_of_scope", "unconfirmed"]


class MedicationIngredient(Frozen):
    """藥名對照出的一個有效成分，及其所屬用藥類別。"""

    code: str
    name_en: str
    name_zh: str
    class_code: str
    class_name_zh: str


class Medication(Frozen):
    """一個用藥：使用者輸入的原文，加上後端對照出的結果（複方有多個有效成分）。"""

    raw_name: str
    scope_status: ScopeStatus
    name_zh: str | None  # 中文藥名；對照不到時為 None
    ingredients: list[MedicationIngredient]
    out_of_scope_names: list[str]  # 認得但不在範圍內的成分名稱


class AssessmentCase(Frozen):
    """評估個案快照：判定引擎的唯一輸入（連同參考資料）。"""

    profile: ProfileSnapshot
    age: int  # 評估當天年齡
    assessed_on: date
    products: list[Product]
    medications: list[Medication] = []  # 空 = 使用者略過用藥


class UlComparison(Frozen):
    """一個目標營養素的上限比對。ul 為 None = 無已知上限攝取量。"""

    nutrient_code: str
    intake: float  # 跨產品加總的單日峰值攝取量（DRIs 單位）；上限比對一律用它
    average_intake: float  # 跨產品加總的平均每日攝取量，只用於一般呈現
    non_daily: bool  # 有非每日服用的產品貢獻此營養素
    unit: str
    ul: float | None
    ul_percent: float | None
    exceeded: bool
    supplement_only: bool  # 鎂、鐵：UL 只計補充劑來源
    estimated: bool = False  # 加總中含系統推估值（非標示值）


class ListedIngredient(Frozen):
    """被保留並在報告中揭露的標示成分（範圍外或無法確認）。"""

    product_name: str
    ingredient_code: str


class NutrientSource(Frozen):
    """一項產品中某個目標營養素的元素量來源。

    只看「有沒有」的交互作用規則用這份清單判斷：source 為 undetermined 時營養素仍算存在。
    """

    product_name: str
    nutrient_code: str
    source: Literal["labeled", "estimated", "undetermined"]
    compound_code: str | None = None  # source 為 estimated 時的化合物


class Assessment(Frozen):
    """判定：確定性程式的產出，報告只能解釋它。"""

    reference_version: str
    ul_comparisons: list[UlComparison]
    out_of_scope_ingredients: list[ListedIngredient]
    unconfirmed_ingredients: list[ListedIngredient]
    undetermined_nutrients: list[str]  # 元素量無法判定、未計入上限比對的營養素
    nutrient_sources: list[NutrientSource] = []  # 各產品目標營養素的來源（標示／推估／無法判定）
    disclosures: list[str]  # 揭露事項代碼，由報告模板渲染
