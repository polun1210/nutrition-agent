"""報告問答 API：對自己的評估個案發問；對話不保存。"""

import logging
from dataclasses import asdict
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, StringConstraints

from nutrition_agent.api.assessments import get_reference
from nutrition_agent.api.deps import (
    User,
    current_user,
    get_chat_model,
    get_connection,
    get_gateway,
)
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference import ReferenceData
from nutrition_agent.retrieval.search import retrieve_evidence
from nutrition_agent.report_chat.agent import ChatTurn, answer_question

router = APIRouter(prefix="/api/assessments")
logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 500
MAX_HISTORY_CONTENT_CHARS = 5000
MODEL_UNAVAILABLE = "問答服務暫時無法使用，請稍後再試"


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=MAX_HISTORY_CONTENT_CHARS)]


class ChatBody(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS)
    ]
    history: list[HistoryMessage] = []


@router.post("/{case_id}/chat")
def chat(
    case_id: int,
    body: ChatBody,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection, scope="function"),
    model: BaseChatModel = Depends(get_chat_model),
    gateway: ModelGateway = Depends(get_gateway),
    ref: ReferenceData = Depends(get_reference),
) -> dict:
    row = conn.execute(
        "SELECT report, assessment FROM assessment_cases WHERE id = %s AND user_id = %s",
        (case_id, user.id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這份評估")
    history = [ChatTurn(m.role, m.content) for m in body.history]

    def retrieve(ingredient_code, drug_codes):
        return retrieve_evidence(conn, gateway, ref, ingredient_code, drug_codes)

    try:
        answer, sources = answer_question(
            model, row[0], row[1], body.question, history, retrieve
        )
    except Exception:
        logger.exception("報告問答的模型呼叫失敗（個案 %s）", case_id)
        raise HTTPException(status_code=502, detail=MODEL_UNAVAILABLE) from None
    return {"answer": answer, "sources": [asdict(s) for s in sources]}
