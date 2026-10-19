from pathlib import Path

import pytest

from nutrition_agent.retrieval.ingest import ingest_corpus
from nutrition_agent.retrieval.search import retrieve_evidence
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
    ranked = [r.section for r in results if r.source_type == "nih_ods_health_professional"]
    assert ranked.index("Interactions with Medications > Levothyroxine") < ranked.index(
        "Introduction"
    )
    mentions = [r for r in results if "levothyroxine" in r.text.lower()]
    others = [r for r in results if "levothyroxine" not in r.text.lower()]
    assert results == mentions + others  # 內文提到該藥的排前面
    for group in (mentions, others):
        sims = [r.similarity for r in group]
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

    assert results
    assert any(
        r.section == "Interactions with Medications > Levothyroxine"
        and "levothyroxine" in r.text.lower()
        for r in results
    )
    assert not any(r.section.lower().startswith("references") for r in results)
    sources = {r.source_type for r in results}
    assert sources <= {"nih_ods_health_professional", "nih_ods_consumer", "dris"}
