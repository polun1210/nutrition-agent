"""個人資料的輸入模型與驗證。"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from nutrition_agent.accounts import validate_conditions


class Profile(BaseModel):
    birth_year: Annotated[int, Field(ge=1900, le=date.today().year)]
    birth_month: Annotated[int, Field(ge=1, le=12)]
    sex: Literal["male", "female"]
    conditions: list[str]

    @field_validator("conditions")
    @classmethod
    def _check_conditions(cls, value: list[str]) -> list[str]:
        return validate_conditions(value)
