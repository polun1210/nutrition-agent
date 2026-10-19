"""判定引擎的輸入（評估個案快照）與輸出（判定）。

輸入是凍結後的快照，輸出由 `assess` 純函數產生。後續的票（用藥、規則、非每天頻率）
在這些模型上加欄位，不改現有欄位的意思。
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class Intake(Frozen):
    """服用方式。目前只有「每天服用」；之後的票在這裡加頻率。"""

    frequency: Literal["daily"] = "daily"
    times_per_day: Annotated[int, Field(ge=1, le=24)]
    units_per_time: PositiveNumber  # 每次幾個劑型單位


class Product(Frozen):
    name: Annotated[str, Field(min_length=1)]
    dose_unit: Literal["粒", "錠", "包", "匙", "毫升"]
    units_per_serving: PositiveNumber  # 每份幾個劑型單位
    ingredients: list[IngredientLine]
    intake: Intake
    photo_ids: list[int] = Field(default_factory=list)  # 標示照片（product_photos.id）


class AssessmentCase(Frozen):
    """評估個案快照：判定引擎的唯一輸入（連同參考資料）。"""

    profile: ProfileSnapshot
    age: int  # 評估當天年齡
    assessed_on: date
    products: list[Product]


class UlComparison(Frozen):
    """一個目標營養素的上限比對。ul 為 None = 無已知上限攝取量。"""

    nutrient_code: str
    intake: float  # 跨產品加總的單日峰值攝取量（DRIs 單位）
    unit: str
    ul: float | None
    ul_percent: float | None
    exceeded: bool
    supplement_only: bool  # 鎂、鐵：UL 只計補充劑來源


class ListedIngredient(Frozen):
    """被保留並在報告中揭露的標示成分（範圍外或無法確認）。"""

    product_name: str
    ingredient_code: str


class Assessment(Frozen):
    """判定：確定性程式的產出，報告只能解釋它。"""

    reference_version: str
    ul_comparisons: list[UlComparison]
    out_of_scope_ingredients: list[ListedIngredient]
    unconfirmed_ingredients: list[ListedIngredient]
    undetermined_nutrients: list[str]  # 單位無法換算、未計入上限比對的營養素
    disclosures: list[str]  # 揭露事項代碼，由報告模板渲染
