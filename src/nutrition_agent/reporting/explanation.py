"""附引用的白話解釋（ADR-0001）：檢索證據 → LLM 白話化 → 輸出檢查 → 腳註。

LLM 只解釋已經產生的判定，每句附證據段落 ID；數值一律由模板渲染。
輸出檢查是純程式：含量值數字、有句子沒引用、引用的 ID 不在這次檢索結果、出現禁用詞，都不合格。
不合格最多重試 MAX_RETRIES 次，仍不合格（或模型、檢索故障）就退回該規則的審定說明文字，
報告一定會完整產出。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Literal

import psycopg
from pydantic import BaseModel, ConfigDict

from nutrition_agent.assessment import Assessment, InteractionFinding
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference import ReferenceData
from nutrition_agent.reference.names import contains_quantity
from nutrition_agent.reporting.forbidden import find_forbidden_terms
from nutrition_agent.retrieval.search import Evidence, retrieve_evidence

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
SOURCE_LABELS = {
    "dris": "DRIs",
    "nih_ods_health_professional": "NIH ODS",
    "nih_ods_consumer": "NIH ODS",
    "nccih": "NCCIH",
    "tfda": "TFDA 仿單",
}

SYSTEM_PROMPT = (
    "你是衛教文字編輯。你只能把「已經判定好的結果」依提供的證據段落改寫成白話中文，"
    "不能新增、修改或否定判定，也不能下診斷。"
)


class ExplainedSentence(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    evidence_ids: list[str] = []  # 審定說明文字（退回模板）沒有證據段落
    footnotes: list[int] = []  # 對應 Report.footnotes 的編號


class FindingExplanation(BaseModel):
    """一張交互作用卡的白話解釋；source=template 表示退回該規則的審定說明文字。"""

    model_config = ConfigDict(frozen=True)

    ingredient_code: str
    source: Literal["llm", "template"]
    sentences: list[ExplainedSentence]


class Footnote(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int
    evidence_id: str
    source_label: str
    document_name: str
    section: str
    text: str


def check_sentences(
    sentences: Sequence[tuple[str, Sequence[str]]], retrieved_ids: set[str]
) -> list[str]:
    """純程式輸出檢查；回傳不合格原因，空 list = 合格。"""
    if not sentences:
        return ["沒有任何句子"]
    problems: list[str] = []
    for text, ids in sentences:
        if contains_quantity(text):
            problems.append(f"含數字：{text}")
        if not ids:
            problems.append(f"沒有附證據段落 ID：{text}")
        unknown = [i for i in ids if i not in retrieved_ids]
        if unknown:
            problems.append(f"引用的 ID 不在檢索結果中：{', '.join(unknown)}")
        problems.extend(f"含禁用詞「{w}」：{text}" for w in find_forbidden_terms(text))
    return problems


def _parse(raw: str) -> list[ExplainedSentence] | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(cleaned)
        return [
            ExplainedSentence(text=str(item["text"]), evidence_ids=[str(i) for i in item["evidence_ids"]])
            for item in data
        ]
    except (ValueError, TypeError, KeyError):
        return None


def _prompt(finding: InteractionFinding, ingredient_name: str, evidence: Sequence[Evidence]) -> str:
    drugs = "、".join(d.raw_name for d in finding.triggering_drugs)
    passages = "\n\n".join(f"[{e.id}] ({e.document_name} / {e.section})\n{e.text}" for e in evidence)
    return (
        f"判定：使用者同時服用「{ingredient_name}」與「{drugs}」，命中已審定的交互作用規則。\n"
        f"審定說明：{'；'.join(finding.reasons_zh)}\n\n"
        f"證據段落：\n{passages}\n\n"
        "請用白話繁體中文寫 1 到 3 句解釋這個判定，規則：\n"
        "- 每一句都必須引用至少一個上面的證據段落 ID，且只能用上面列出的 ID。\n"
        "- 不得出現任何數字或數量，中文數字也算（例如「一年」「兩粒」），數值由系統另外呈現；成分與藥品名稱本身可以寫。\n"
        "- 不得說「安全」「未發現問題」，不得下診斷，不得建議劑量、停用或購買。\n"
        '只輸出 JSON 陣列，例如：[{"text": "…", "evidence_ids": ["ev-…"]}]'
    )


def explain_finding(
    gateway: ModelGateway,
    finding: InteractionFinding,
    ingredient_name: str,
    evidence: Sequence[Evidence],
) -> list[ExplainedSentence] | None:
    """產生並檢查一個判定的解釋；不合格最多重試 MAX_RETRIES 次，仍不合格回傳 None。"""
    if not evidence:
        return None
    retrieved = {e.id for e in evidence}
    prompt = _prompt(finding, ingredient_name, evidence)
    for attempt in range(1 + MAX_RETRIES):
        try:
            sentences = _parse(gateway.complete(prompt, system=SYSTEM_PROMPT))
        except Exception:  # 模型服務故障算一次不合格，不能讓報告產不出來
            logger.exception("產生白話解釋失敗（第 %d 次）", attempt + 1)
            continue
        if sentences is not None and not check_sentences(
            [(s.text, s.evidence_ids) for s in sentences], retrieved
        ):
            return sentences
    return None


def _retrieve(
    conn: psycopg.Connection, gateway: ModelGateway, finding: InteractionFinding
) -> list[Evidence]:
    drug_codes = list(dict.fromkeys(d.ingredient_code for d in finding.triggering_drugs))
    try:
        with conn.transaction():  # 失敗時只回到 savepoint，不污染外層交易
            return retrieve_evidence(conn, gateway, finding.ingredient_code, drug_codes)
    except Exception:
        logger.exception("檢索證據失敗：%s", finding.ingredient_code)
        return []


def build_explanations(
    conn: psycopg.Connection,
    gateway: ModelGateway,
    assessment: Assessment,
    ref: ReferenceData,
) -> tuple[list[FindingExplanation], list[Footnote]]:
    """替每張交互作用卡產生解釋，並依首次出現順序給全報告統一的腳註編號。"""
    explanations: list[FindingExplanation] = []
    numbers: dict[str, int] = {}
    footnote_sources: dict[str, Evidence] = {}
    for finding in assessment.interactions:
        evidence = _retrieve(conn, gateway, finding)
        by_id = {e.id: e for e in evidence}
        ingredient = ref.ingredients.get(finding.ingredient_code)
        name = ingredient.display_name_zh if ingredient else finding.ingredient_code
        sentences = explain_finding(gateway, finding, name, evidence)
        if sentences is None:
            explanations.append(
                FindingExplanation(
                    ingredient_code=finding.ingredient_code,
                    source="template",
                    sentences=[ExplainedSentence(text=t) for t in finding.reasons_zh],
                )
            )
            continue
        numbered = []
        for s in sentences:
            for ev_id in s.evidence_ids:
                numbers.setdefault(ev_id, len(numbers) + 1)
                footnote_sources.setdefault(ev_id, by_id[ev_id])
            numbered.append(
                s.model_copy(update={"footnotes": [numbers[i] for i in s.evidence_ids]})
            )
        explanations.append(
            FindingExplanation(
                ingredient_code=finding.ingredient_code, source="llm", sentences=numbered
            )
        )
    return explanations, _footnotes(numbers, footnote_sources)


def _footnotes(numbers: dict[str, int], sources: dict[str, Evidence]) -> list[Footnote]:
    return [
        Footnote(
            number=number,
            evidence_id=ev_id,
            source_label=SOURCE_LABELS.get(sources[ev_id].source_type, sources[ev_id].source_type),
            document_name=sources[ev_id].document_name,
            section=sources[ev_id].section,
            text=sources[ev_id].text,
        )
        for ev_id, number in numbers.items()
    ]


__all__: Iterable[str] = [
    "MAX_RETRIES",
    "ExplainedSentence",
    "FindingExplanation",
    "Footnote",
    "build_explanations",
    "check_sentences",
    "explain_finding",
]
