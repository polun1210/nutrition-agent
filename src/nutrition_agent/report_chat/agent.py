"""報告問答的 ReAct agent（ADR-0008）：模型自己決定要不要呼叫工具。

agent 每個請求依個案建立（工具綁定這份個案，模型不能指定其他個案）；聊天模型整個行程共用。
"""

from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from nutrition_agent.report_chat.findings import build_findings

# 只保留最後 3 輪（6 則訊息）的歷史。
MAX_HISTORY_MESSAGES = 6

SYSTEM_PROMPT = """你是「補對了嗎？」保健食品與慢性病用藥評估報告的問答助理，回答使用者針對自己這份評估個案的追問。

規則：
- 判定以報告為準，不可推翻或改變。使用者主張與判定矛盾時，依 get_findings 的內容說明，不要附和。
- 回答前先用 get_findings 讀取這份個案的判定，不要憑空猜測個案內容。
- 可以直接引用判定裡的數字（攝取量、上限、百分比）。
- 沒有命中交互作用規則時，就說這份報告沒有命中，不要編造。
- 問到評估範圍外的成分或藥物時，誠實說明不在評估範圍內。
- 用到模型自己的一般知識時，要明說「這部分不是出自系統語料」。
- 使用繁體中文，回答簡潔。
- 詞彙依專案詞彙表：說「補充劑來源攝取量」，不說「攝取量缺口」；來源是報告上顯示的名稱。
"""


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


def answer_question(
    model: BaseChatModel, report: dict, question: str, history: list[ChatTurn]
) -> str:
    @tool
    def get_findings() -> str:
        """取得這份評估個案的判定：命中的交互作用規則與建議行動、各營養素的上限比對、保健食品與用藥、評估範圍。"""
        return build_findings(report)

    agent = create_react_agent(model, [get_findings], prompt=SYSTEM_PROMPT)
    messages = [
        (turn.role, turn.content) for turn in history[-MAX_HISTORY_MESSAGES:]
    ] + [("user", question)]
    result = agent.invoke({"messages": messages})
    return _text(result["messages"][-1].content)


def _text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
