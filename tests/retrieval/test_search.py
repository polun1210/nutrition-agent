from collections import Counter
from pathlib import Path

import pytest

from nutrition_agent.retrieval.ingest import ingest_corpus
from nutrition_agent.retrieval.search import MAX_CHUNKS_PER_DOCUMENT, retrieve_evidence
from tests.retrieval.fakes import BagOfWordsGateway

REPO_KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def corpus(db, tmp_path):
    _write(
        tmp_path,
        "sources/nih_ods/Calcium-HealthProfessional.md",
        "# Calcium\n\n## Introduction\n\nCalcium builds bones and teeth.\n\n"
        "## Interactions with Medications\n\n### Levothyroxine\n\n"
        "Calcium carbonate reduces levothyroxine absorption; separate by 4 hours.\n\n"
        "### Quinolone antibiotics\n\nCalcium binds quinolone antibiotics.\n",
    )
    _write(
        tmp_path,
        "sources/nih_ods/Zinc-HealthProfessional.md",
        "# Zinc\n\n## Interactions with Medications\n\nZinc reduces levothyroxine absorption.\n",
    )
    _write(
        tmp_path,
        "raw/tfda/甲狀腺/Levothyroxine/L1_20250101.md",
        "【交互作用】\nLevothyroxine 與鈣劑併用會降低吸收，應間隔服用。\n",
    )
    ingest_corpus(db, BagOfWordsGateway(), tmp_path)
    return tmp_path


def test_retrieval_filters_by_ingredient_then_ranks_by_similarity(db, corpus):
    results = retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"])

    assert results
    assert all("zinc" not in r.ingredients for r in results)
    # 假 embedding 只比字詞重疊，語意排序的品質由 evals/rag 用真模型量。
    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True)


def test_retrieval_includes_drug_label_for_the_given_drug(db, corpus):
    results = retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"])
    assert "tfda" in {r.source_type for r in results}


def test_evidence_ids_are_stable_across_reingest(db, corpus):
    first = [r.id for r in retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"])]
    ingest_corpus(db, BagOfWordsGateway(), corpus)
    second = [r.id for r in retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"])]
    assert first == second


def test_limit_caps_results(db, corpus):
    assert len(retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"], limit=1)) == 1


def test_unknown_ingredient_returns_nothing(db, corpus):
    assert retrieve_evidence(db, BagOfWordsGateway(), "selenium", []) == []


def test_existing_corpus_alone_answers_calcium_levothyroxine(db):
    """只靠 repo 內建語料（DRIs、NIH ODS）就能跑通。"""
    ingest_corpus(db, BagOfWordsGateway(), REPO_KNOWLEDGE)

    results = retrieve_evidence(db, BagOfWordsGateway(), "calcium", ["levothyroxine"], limit=50)

    assert "sources/nih_ods/Calcium-HealthProfessional.md" in {r.document_path for r in results}
    assert not any(r.section.lower().startswith("references") for r in results)
    sources = {r.source_type for r in results}
    assert sources <= {"nih_ods_health_professional", "nih_ods_consumer", "dris"}


def test_one_long_drug_label_cannot_fill_all_results(db, tmp_path):
    """仿單每段都含藥名；不能讓單一文件佔滿結果，把營養素文件的交互作用段落擠掉。"""
    label = "".join(f"【第{i}節】\nIndapamide 吲達帕胺 說明 {i}。\n\n" for i in range(10))
    _write(tmp_path, "raw/tfda/高血壓/Indapamide/L1_20250101.md", label)
    _write(
        tmp_path,
        "sources/nih_ods/Zinc-HealthProfessional.md",
        "# Zinc\n\n## Interactions with Medications\n\n"
        "Thiazide diuretics increase zinc excretion in the urine.\n",
    )
    ingest_corpus(db, BagOfWordsGateway(), tmp_path)

    results = retrieve_evidence(db, BagOfWordsGateway(), "zinc", ["indapamide"], limit=3)

    per_document = Counter(r.document_path for r in results)
    assert per_document["raw/tfda/高血壓/Indapamide/L1_20250101.md"] == MAX_CHUNKS_PER_DOCUMENT
    assert "sources/nih_ods/Zinc-HealthProfessional.md" in per_document


def test_few_documents_still_fill_the_limit(db, tmp_path):
    """每份文件的名額只是優先順序：文件不夠多時，照相似度補滿 limit。"""
    label = "".join(f"【第{i}節】\nIndapamide 吲達帕胺 說明 {i}。\n\n" for i in range(10))
    _write(tmp_path, "raw/tfda/高血壓/Indapamide/L1_20250101.md", label)
    ingest_corpus(db, BagOfWordsGateway(), tmp_path)

    results = retrieve_evidence(db, BagOfWordsGateway(), "zinc", ["indapamide"], limit=5)

    assert len(results) == 5
    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True)


def test_query_names_the_nutrient_drug_and_drug_class(db, corpus):
    gateway = BagOfWordsGateway()

    retrieve_evidence(db, gateway, "zinc", ["indapamide"])

    query = gateway.embedded[-1]
    for expected in ("鋅", "Zinc", "Indapamide", "吲達帕胺", "thiazide diuretic"):
        assert expected in query
