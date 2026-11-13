"""get_findings 的內容：這份評估個案已存的報告，整理成給模型讀的文字。

只讀個案凍結的報告（顯示名稱、顯示單位都已在裡面），不重新判定、不呼叫模型。
"""

import json

# 前端分組用的欄位，對回答沒有幫助，不給模型。
_UI_ONLY_KEYS = {"groups", "drug_groups", "notes"}


def build_findings(report: dict) -> str:
    sections = [
        {k: v for k, v in section.items() if k not in _UI_ONLY_KEYS and v}
        for section in report["sections"]
    ]
    explanations = [
        {
            "ingredient_code": e["ingredient_code"],
            "text": "".join(s["text"] for s in e["sentences"]),
        }
        for e in report.get("explanations", [])
    ]
    return json.dumps(
        {"sections": sections, "explanations": explanations}, ensure_ascii=False, indent=1
    )
