"""報告問答的 ReAct agent（ADR-0008）：模型自己決定要不要呼叫工具。

agent 每個請求依個案建立（工具綁定這份個案，模型不能指定其他個案）；聊天模型整個行程共用。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from nutrition_agent.report_chat.findings import build_findings
from nutrition_agent.reporting.explanation import SOURCE_LABELS
from nutrition_agent.retrieval.search import Evidence

# (成分代碼, 藥物有效成分代碼) -> 證據段落
Retriever = Callable[[str, Sequence[str]], list[Evidence]]

# 只保留最後 3 輪（6 則訊息）的歷史。
MAX_HISTORY_MESSAGES = 6

SYSTEM_PROMPT = """你是「補對了嗎？」保健食品與慢性病用藥評估報告的問答助理，回答使用者針對自己這份評估個案的追問。

規則：
- 判定以報告為準，不可推翻或改變。使用者主張與判定矛盾時，依 get_findings 的內容說明，不要附和。
- 回答前先用 get_findings 讀取這份個案的判定，不要憑空猜測個案內容。
- 需要依據時，用 search_evidence 檢索系統語料；代碼只能用 get_findings 的 searchable_evidence 列出的。用到檢索段落時，回答要能對上來源（來源清單由系統附上）。
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


@dataclass(frozen=True)
class Source:
    source_label: str
    document_name: str
    section: str
    text: str


def answer_question(
    model: BaseChatModel,
    report: dict,
    assessment: dict,
    question: str,
    history: list[ChatTurn],
    retrieve: Retriever,
) -> tuple[str, list[Source]]:
    sources: dict[str, Source] = {}  # 以證據 ID 去重，保留第一次出現的順序

    @tool
    def get_findings() -> str:
        """取得這份評估個案的判定：命中的交互作用規則與建議行動、各營養素的上限比對、保健食品與用藥、評估範圍，以及 search_evidence 可用的代碼。"""
        return build_findings(report, assessment)

    @tool
    def search_evidence(ingredient_code: str, drug_ingredient_codes: list[str] | None = None) -> str:
        """檢索系統語料的證據段落。ingredient_code 是一個成分代碼；drug_ingredient_codes 是選填的藥物有效成分代碼。可用的代碼見 get_findings 的 searchable_evidence。"""
        evidence = retrieve(ingredient_code, drug_ingredient_codes or [])
        for e in evidence:
            sources.setdefault(e.id, _source(e))
        if not evidence:
            return "沒有找到相關的證據段落。"
        return "\n\n".join(
            f"[{_source(e).source_label}｜{e.document_name}｜{e.section}]\n{e.text}"
            for e in evidence
        )

    agent = create_react_agent(model, [get_findings, search_evidence], prompt=SYSTEM_PROMPT)
    messages = [
        (turn.role, turn.content) for turn in history[-MAX_HISTORY_MESSAGES:]
    ] + [("user", question)]
    result = agent.invoke({"messages": messages})
    return _text(result["messages"][-1].content), list(sources.values())


def _source(e: Evidence) -> Source:
    label = SOURCE_LABELS.get(e.source_type, e.source_type)
    return Source(label, e.document_name, e.section, e.text)


def _text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
