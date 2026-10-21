"""報告禁用詞檢查：不得宣稱安全或確診，也不得給劑量、停用、購買的指示。

純函數，報告全文（模板渲染後；之後 LLM 解釋也一樣）都可以丟進來檢查。
"""

from __future__ import annotations

import re

FORBIDDEN_TERMS = (
    "安全",
    "未發現問題",
    "確診",
    "劑量",
    "停用",
    "停藥",
    "停止服用",
    "購買",
    "建議服用",
    "建議每天",
    "增加服用",
    "減少服用",
)


# 「專家建議服用此類藥物的人應監測血鉀」：建議的對象是服藥的人，不是叫使用者服用。
# 只遮掉這個句型裡的「建議服用」四個字，句子其餘部分照常檢查。
_ADVICE_TO_TAKERS = re.compile(r"建議服用(?=[^，。；、,.;!?！？\s]{0,15}?(?:的人|者))")

# 「高劑量菸鹼酸可能升高血糖」是轉述證據；「調整劑量」「建議劑量」才是劑量指示，照常擋。
_HIGH_DOSE = re.compile(r"[高大]劑量")


def find_forbidden_terms(text: str) -> list[str]:
    """回傳 text 裡出現的禁用詞（依 FORBIDDEN_TERMS 順序）；空 list = 通過。"""
    checked = _HIGH_DOSE.sub("｜", _ADVICE_TO_TAKERS.sub("｜", text))
    return [term for term in FORBIDDEN_TERMS if term in checked]
