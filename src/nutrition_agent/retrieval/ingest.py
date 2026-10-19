"""語料 ingest：去重、去圖、切塊、產生 embedding 並寫入 pgvector（冪等）。

用法：`uv run python -m nutrition_agent.retrieval.ingest [knowledge_dir]`
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.ingredients import normalize_name
from nutrition_agent.retrieval.chunking import Chunk, chunk_markdown, strip_base64_images
from nutrition_agent.retrieval.corpus import Document, discover_documents

EMBED_BATCH_SIZE = 64
MAX_EMBED_CHARS = 2000
NUL = chr(0)  # PostgreSQL text 欄位不接受 NUL
_MD_LINK_TARGET = re.compile(r"\]\([^)]*\)")
# 參考文獻、免責聲明不是證據，不進索引。
_NOISE_SECTIONS = frozenset({"references", "disclaimer", "top"})


@dataclass(frozen=True)
class IngestResult:
    documents: int
    added: int
    removed: int


@dataclass(frozen=True)
class _PreparedChunk:
    id: str
    chunk: Chunk
    ingredients: tuple[str, ...]


def chunk_id(relative_path: str, section: str, text: str) -> str:
    """穩定 ID：同一份文件、同一章節、同樣內容永遠得到同一個 ID。"""
    digest = hashlib.sha1(f"{relative_path}\0{section}\0{text}".encode()).hexdigest()
    return f"ev-{digest[:16]}"


def ingest_corpus(
    conn: psycopg.Connection, gateway: ModelGateway, knowledge_dir: Path
) -> IngestResult:
    knowledge_dir = Path(knowledge_dir)
    documents = list(discover_documents(knowledge_dir))
    added = removed = 0
    for document in documents:
        prepared = _prepare(document)
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM evidence_chunk WHERE document_path = %s",
                (document.relative_path,),
            )
        }
        new = [p for p in prepared if p.id not in existing]
        stale = existing - {p.id for p in prepared}
        _insert(conn, gateway, document, new)
        if stale:
            conn.execute("DELETE FROM evidence_chunk WHERE id = ANY(%s)", (sorted(stale),))
        added += len(new)
        removed += len(stale)
    return IngestResult(documents=len(documents), added=added, removed=removed)


def _prepare(document: Document) -> list[_PreparedChunk]:
    raw_text = document.path.read_text(encoding="utf-8")
    text = strip_base64_images(raw_text.replace(NUL, ""))
    seen: set[str] = set()
    prepared: list[_PreparedChunk] = []
    for chunk in chunk_markdown(text):
        if chunk.section.split(" > ")[0].strip().lower() in _NOISE_SECTIONS:
            continue
        cid = chunk_id(document.relative_path, chunk.section, chunk.text)
        if cid in seen:  # 同文件內完全相同的段落只留一份
            continue
        seen.add(cid)
        ingredients = (
            _ingredients_mentioned(chunk.text) if document.tag_by_content else document.ingredients
        )
        prepared.append(_PreparedChunk(cid, chunk, ingredients))
    return prepared


def _ingredients_mentioned(text: str) -> tuple[str, ...]:
    """DRIs 沒有逐成分的檔案：以成分顯示名稱與同義詞是否出現在段落中標記。"""
    haystack = normalize_name(text)
    found = [
        ing.code
        for ing in load_reference_data().ingredients.ingredients
        if any(normalize_name(n) in haystack for n in (ing.display_name_zh, *ing.synonyms))
    ]
    return tuple(found)


def _embedding_input(document: Document, chunk: Chunk) -> str:
    body = _MD_LINK_TARGET.sub("]", chunk.text)
    return f"{document.name} / {chunk.section}\n{body}"[:MAX_EMBED_CHARS]


def _insert(
    conn: psycopg.Connection,
    gateway: ModelGateway,
    document: Document,
    prepared: list[_PreparedChunk],
) -> None:
    for offset in range(0, len(prepared), EMBED_BATCH_SIZE):
        batch = prepared[offset : offset + EMBED_BATCH_SIZE]
        vectors = gateway.embed([_embedding_input(document, p.chunk) for p in batch])
        if len(vectors) != len(batch):
            raise RuntimeError("embedding 數量與切塊數量不符")
        for item, vector in zip(batch, vectors, strict=True):
            conn.execute(
                "INSERT INTO evidence_chunk (id, source_type, document_name, document_path, "
                "ingredients, section, start_char, end_char, start_line, end_line, text, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)",
                (
                    item.id,
                    document.source_type,
                    document.name,
                    document.relative_path,
                    list(item.ingredients),
                    item.chunk.section,
                    item.chunk.start,
                    item.chunk.end,
                    item.chunk.start_line,
                    item.chunk.end_line,
                    item.chunk.text,
                    vector_literal(vector),
                ),
            )


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def main(argv: list[str]) -> int:
    from nutrition_agent.config import get_settings
    from nutrition_agent.gateway import OpenRouterGateway

    knowledge_dir = Path(argv[1]) if len(argv) > 1 else Path("knowledge")
    settings = get_settings()
    gateway = OpenRouterGateway.from_settings(settings)
    with psycopg.connect(settings.database_url) as conn:
        result = ingest_corpus(conn, gateway, knowledge_dir)
    print(f"文件 {result.documents} 份，新增 {result.added} 塊，移除 {result.removed} 塊")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
