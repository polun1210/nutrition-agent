"""交互作用規則與出處的資料格式（草稿／審定／退役）。

單條規則的不變式在建構時就會被擋下；跨檔的檢查（出處逐字存在、成分存在於目錄等）在 checks.py。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nutrition_agent.reference.names import contains_quantity_digit


class RuleStatus(StrEnum):
    DRAFT = "draft"  # 草稿：可由 agent 草擬，不進入判定
    APPROVED = "approved"  # 審定：只能由開發者手動標記，判定引擎只讀這一種
    RETIRED = "retired"  # 退役


class ConditionType(StrEnum):
    DRUG_CLASS = "drug_class"
    DRUG_INGREDIENT = "drug_ingredient"


class InteractionType(StrEnum):
    ABSORPTION = "absorption"  # 吸收干擾
    PHARMACODYNAMIC = "pharmacodynamic"  # 藥效交互
    DRUG_AFFECTS_NUTRIENT = "drug_affects_nutrient"  # 藥物影響營養素


class Advice(StrEnum):
    """建議行動的封閉列舉：沒有也不得新增「停用」「減量」「改吃某產品」。"""

    SEPARATE_TIMING = "separate_timing"
    INFORM_PROVIDER = "inform_provider"
    CONSULT_BEFORE_COMBINING = "consult_before_combining"


class SourceType(StrEnum):
    """規則出處只接受這三種；NIH ODS 只接受 HealthProfessional 版，Consumer 版不算。"""

    TFDA_LABEL = "tfda_label"
    NIH_ODS_HP = "nih_ods_hp"
    NCCIH = "nccih"


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: SourceType
    document: str  # 相對於 knowledge/ 的路徑
    quote: str  # 逐字引文

    @field_validator("document", "quote")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("出處的 document 與 quote 不可空白")
        return value


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    condition_type: ConditionType
    condition_code: str
    ingredient_code: str
    ingredient_form: str | None = None  # 限定成分型態＝化合物表代碼（例如 magnesium_oxide），與成分行的 compound_code 比對；None = 不限
    interaction_type: InteractionType
    requires_supplement_intake: bool
    advice: Advice
    separation_hours: int | None = None
    reason_zh: str
    status: RuleStatus
    approved_by: str | None = None
    citations: tuple[Citation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _invariants(self) -> Self:
        affects = self.interaction_type is InteractionType.DRUG_AFFECTS_NUTRIENT
        if affects == self.requires_supplement_intake:
            raise ValueError(f"{self.id}: 「藥物影響營養素」⟺ 不需要使用者有補充")
        separate = self.advice is Advice.SEPARATE_TIMING
        if separate != (self.separation_hours is not None):
            raise ValueError(f"{self.id}: 錯開時數 ⟺ 建議行動是錯開服用")
        if contains_quantity_digit(self.reason_zh):
            raise ValueError(f"{self.id}: 規則說明文字不得含數字")
        approved = self.status is RuleStatus.APPROVED
        if approved != bool(self.approved_by):
            raise ValueError(f"{self.id}: 審定規則必須有審定者，其他狀態不能有")
        return self


class RuleSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    rules: tuple[Rule, ...] = ()

    def approved(self) -> tuple[Rule, ...]:
        """判定引擎唯一該讀的規則。"""
        return tuple(r for r in self.rules if r.status is RuleStatus.APPROVED)
