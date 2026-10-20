"""證據段落檢索：先用後設資料（成分、藥）篩選，再依 embedding 相似度排序。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import psycopg

from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference import load_reference_data

DEFAULT_LIMIT = 8
MAX_CHUNKS_PER_DOCUMENT = 2


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
    排序：與查詢文字的餘弦相似度；查詢文字列出成分、藥與藥物類別的中英文名稱，
    讓只寫類別（例如 "thiazide diuretics"）的證據也找得到。
    入選順序：每份文件相似度前 MAX_CHUNKS_PER_DOCUMENT 段優先，名額有剩再依相似度補滿；
    仿單每段都提到藥名，不這樣分配會佔滿結果。回傳時依相似度排序。
    """
    from nutrition_agent.retrieval.ingest import vector_literal

    codes = [ingredient_code, *drug_ingredient_codes]
    (query_vector,) = gateway.embed([_query_text(ingredient_code, drug_ingredient_codes)])
    rows = conn.execute(
        "WITH ranked AS ("
        "SELECT id, source_type, document_name, document_path, ingredients, section, "
        "start_line, end_line, text, 1 - (embedding <=> %(vector)s::vector) AS similarity, "
        "row_number() OVER (PARTITION BY document_path "
        "ORDER BY embedding <=> %(vector)s::vector, id) AS rank_in_document "
        "FROM evidence_chunk WHERE ingredients && %(codes)s::text[]), "
        "chosen AS (SELECT * FROM ranked "
        "ORDER BY rank_in_document > %(per_document)s, similarity DESC, id LIMIT %(limit)s) "
        "SELECT id, source_type, document_name, document_path, ingredients, section, "
        "start_line, end_line, text, similarity FROM chosen ORDER BY similarity DESC, id",
        {
            "vector": vector_literal(query_vector),
            "codes": codes,
            "per_document": MAX_CHUNKS_PER_DOCUMENT,
            "limit": limit,
        },
    ).fetchall()
    return [Evidence(*row[:4], tuple(row[4]), *row[5:]) for row in rows]


def _query_text(ingredient_code: str, drug_ingredient_codes: Sequence[str]) -> str:
    """查詢文字：成分的中文名與英文同義詞，藥的中英文名與類別；目錄外的代碼照原樣放入。"""
    reference = load_reference_data()
    ingredients = {i.code: i for i in reference.ingredients.ingredients}
    drugs = {d.code: d for d in reference.drugs.ingredients}
    parts: list[str] = []
    ingredient = ingredients.get(ingredient_code)
    if ingredient is None:
        parts.append(ingredient_code)
    else:
        parts.append(ingredient.display_name_zh)
        parts.extend(name for name in ingredient.synonyms if name.isascii())
    for code in drug_ingredient_codes:
        drug = drugs.get(code)
        if drug is None:
            parts.append(code)
            continue
        parts.extend([drug.name_en, drug.name_zh])
        if drug.class_code:
            drug_class = reference.drugs.get_class(drug.class_code)
            parts.extend([drug.class_code.replace("_", " "), drug_class.name_zh])
    return " ".join([*parts, "drug interaction 交互作用"])
