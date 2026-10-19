"""證據段落檢索：先用後設資料（成分、藥）篩選，再依 embedding 相似度排序。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import psycopg

from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference import load_reference_data

DEFAULT_LIMIT = 8


@dataclass(frozen=True)
class Evidence:
    id: str  # 穩定 ID；重跑 ingest 後不變
    source_type: str
    document_name: str
    document_path: str  # 相對 knowledge/
    ingredients: tuple[str, ...]
    section: str
    start_line: int
    end_line: int
    text: str
    similarity: float  # 餘弦相似度，越大越相近


def retrieve_evidence(
    conn: psycopg.Connection,
    gateway: ModelGateway,
    ingredient_code: str,
    drug_ingredient_codes: Sequence[str],
    limit: int = DEFAULT_LIMIT,
) -> list[Evidence]:
    """替一個判定（成分＋藥）找證據段落。

    篩選條件：段落標記的成分或有效成分，至少有一個在 (成分, 藥) 之中。
    排序：內文提到該藥名稱的段落優先，其次是與「成分 + 藥 交互作用」查詢文字的餘弦相似度。
    """
    from nutrition_agent.retrieval.ingest import vector_literal

    codes = [ingredient_code, *drug_ingredient_codes]
    query = f"{' '.join(codes)} interaction medication 交互作用"
    (query_vector,) = gateway.embed([query])
    rows = conn.execute(
        "SELECT id, source_type, document_name, document_path, ingredients, section, "
        "start_line, end_line, text, 1 - (embedding <=> %s::vector) AS similarity "
        "FROM evidence_chunk WHERE ingredients && %s::text[] "
        "ORDER BY (text ILIKE ANY(%s)) DESC, embedding <=> %s::vector, id LIMIT %s",
        (
            vector_literal(query_vector),
            codes,
            [f"%{name}%" for name in _drug_names(drug_ingredient_codes)],
            vector_literal(query_vector),
            limit,
        ),
    ).fetchall()
    return [Evidence(*row[:4], tuple(row[4]), *row[5:]) for row in rows]


def _drug_names(drug_ingredient_codes: Sequence[str]) -> list[str]:
    """藥的比對字樣：代碼，加上目錄中的英文與中文名稱。"""
    catalog = {i.code: i for i in load_reference_data().drugs.ingredients}
    names: list[str] = []
    for code in drug_ingredient_codes:
        names.append(code)
        if code in catalog:
            names.extend([catalog[code].name_en, catalog[code].name_zh])
    return names
