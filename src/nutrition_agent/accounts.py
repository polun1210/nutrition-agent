"""帳號領域規則：年齡計算、成年門檻、個人資料的合法值。"""

from datetime import date

ADULT_AGE = 19

SEXES = ("male", "female")
NO_CONDITION = "none"
CONDITIONS = (
    "hypertension",
    "type2_diabetes",
    "hyperlipidemia",
    "chronic_arthritis",
    "chronic_insomnia",
)


class UnderageError(Exception):
    """評估當天未滿 19 歲，無法使用評估。"""


def age_on(birth_year: int, birth_month: int, on: date) -> int:
    """依指定日期算足歲。只有出生年月，視為出生月份起算滿一歲。"""
    return on.year - birth_year - (1 if on.month < birth_month else 0)


def require_adult(birth_year: int, birth_month: int, on: date) -> int:
    """回傳評估當天年齡；未滿 19 歲丟 UnderageError。由評估流程呼叫。"""
    age = age_on(birth_year, birth_month, on)
    if age < ADULT_AGE:
        raise UnderageError(
            f"評估當天未滿 {ADULT_AGE} 歲（目前 {age} 歲），"
            f"無法使用本服務：DRIs 參考值不適用未成年人。"
        )
    return age


def validate_conditions(conditions: list[str]) -> list[str]:
    """已知疾病必答；「以上皆無」與 5 種慢性病互斥。回傳去重後的清單。"""
    unique = list(dict.fromkeys(conditions))
    if not unique:
        raise ValueError("已知疾病必須作答，沒有請選「以上皆無」")
    if NO_CONDITION in unique:
        if len(unique) > 1:
            raise ValueError("「以上皆無」不能和慢性病同時勾選")
        return unique
    unknown = [c for c in unique if c not in CONDITIONS]
    if unknown:
        raise ValueError(f"不支援的已知疾病：{unknown}")
    return unique
