"""報告禁用詞檢查：不得宣稱安全或確診，也不得給劑量、停用、購買的指示。

純函數，報告全文（模板渲染後；之後 LLM 解釋也一樣）都可以丟進來檢查。
"""

from __future__ import annotations

FORBIDDEN_TERMS = (
    "安全",
    "未發現問題",
    "確診",
    "劑量",
    "停用",
    "停止服用",
    "購買",
    "建議服用",
    "建議每天",
    "增加服用",
    "減少服用",
)


def find_forbidden_terms(text: str) -> list[str]:
    """回傳 text 裡出現的禁用詞（依 FORBIDDEN_TERMS 順序）；空 list = 通過。"""
    return [term for term in FORBIDDEN_TERMS if term in text]
