"""RAG eval 的資料格式與計分（離線）；打真模型的部分在 evals/rag/run.py。"""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from nutrition_agent.retrieval.evaluation import (
    ExpectedEvidence,
    load_cases,
    score_points,
    score_retrieval,
    validate_against_corpus,
)
from tests.reporting.test_explanation import evidence

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "rag" / "cases.json"


def test_shipped_cases_load_and_their_expected_text_exists_in_the_corpus():
    cases = load_cases(CASES)

    assert len(cases) >= 3
    for case in cases:
        assert validate_against_corpus(case, ROOT / "knowledge") == [], case.id


def test_validation_reports_missing_expected_text(tmp_path):
    (tmp_path / "a.md").write_text("Metformin reduces B12 absorption.", encoding="utf-8")
    case = load_cases(CASES)[0].model_copy(
        update={"expected_evidence": [ExpectedEvidence(document_path="a.md", contains="nonexistent")]}
    )

    assert validate_against_corpus(case, tmp_path)


def test_retrieval_score_counts_expected_passages_found():
    case = load_cases(CASES)[0]
    expected = case.expected_evidence[0]
    hit = replace(
        evidence(), document_path=expected.document_path, text=f"... {expected.contains} ..."
    )

    assert score_retrieval(case, [hit]).found == 1
    assert score_retrieval(case, [replace(evidence(), text="unrelated")]).found == 0
    assert score_retrieval(case, []).total == len(case.expected_evidence)


def test_points_score_matches_any_keyword_per_point():
    case = load_cases(CASES)[0]
    text = " ".join(kw for point in case.expected_points for kw in point.any_of[:1])

    assert score_points(case, text).found == len(case.expected_points)
    assert score_points(case, "完全無關").found == 0


def test_dry_run_harness_validates_cases_without_network():
    result = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "rag" / "run.py"), "--dry-run"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
