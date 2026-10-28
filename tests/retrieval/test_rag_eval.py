"""RAG eval 的資料格式與計分（離線）；打真模型的部分在 evals/rag/run.py。"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

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


def _check_expected_evidence(case, expected, knowledge):
    # 只略過未安裝的原始語料；已安裝但缺檔、或已收錄的來源缺檔都必須失敗。
    if (
        Path(expected.document_path).parts[:2] == ("raw", "tfda")
        and not (knowledge / "raw" / "tfda").exists()
    ):
        pytest.skip(f"未安裝不隨 Git 提供的語料 raw/tfda：{expected.document_path}")
    selected = case.model_copy(update={"expected_evidence": [expected]})
    assert validate_against_corpus(selected, knowledge) == [], case.id


def test_shipped_cases_load():
    assert len(load_cases(CASES)) >= 3


@pytest.mark.parametrize(
    ("case", "expected"),
    [(case, expected) for case in load_cases(CASES) for expected in case.expected_evidence],
    ids=[
        f"{case.id}:{expected.document_path}"
        for case in load_cases(CASES)
        for expected in case.expected_evidence
    ],
)
def test_shipped_expected_text_exists_in_the_corpus(case, expected):
    _check_expected_evidence(case, expected, ROOT / "knowledge")


def test_raw_evidence_is_explicitly_skipped_when_corpus_is_not_installed(tmp_path):
    case = load_cases(CASES)[0]
    expected = ExpectedEvidence(document_path="raw/tfda/drug/label.md", contains="B12")

    with pytest.raises(pytest.skip.Exception, match="raw/tfda"):
        _check_expected_evidence(case, expected, tmp_path)


def test_missing_source_or_installed_raw_document_still_fails(tmp_path):
    case = load_cases(CASES)[0]
    (tmp_path / "raw" / "tfda").mkdir(parents=True)

    for path in ("sources/missing.md", "raw/tfda/drug/missing.md"):
        expected = ExpectedEvidence(document_path=path, contains="B12")
        with pytest.raises(AssertionError, match=case.id):
            _check_expected_evidence(case, expected, tmp_path)


def test_missing_source_still_fails_without_raw_corpus(tmp_path):
    case = load_cases(CASES)[0]
    expected = ExpectedEvidence(document_path="sources/missing.md", contains="B12")

    with pytest.raises(AssertionError, match=case.id):
        _check_expected_evidence(case, expected, tmp_path)


def test_installed_raw_evidence_is_checked_for_expected_text(tmp_path):
    case = load_cases(CASES)[0]
    document = tmp_path / "raw" / "tfda" / "label.md"
    document.parent.mkdir(parents=True)
    document.write_text("Metformin reduces B12 absorption.", encoding="utf-8")
    expected = ExpectedEvidence(document_path="raw/tfda/label.md", contains="B12")

    _check_expected_evidence(case, expected, tmp_path)

    document.write_text("unrelated", encoding="utf-8")
    with pytest.raises(AssertionError, match=case.id):
        _check_expected_evidence(case, expected, tmp_path)


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


@pytest.mark.parametrize("problem", [None, "missing-source", "missing-raw", "wrong-text"])
def test_dry_run_harness_validates_cases_without_network(tmp_path, problem):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    document_path = "raw/tfda/label.md" if problem == "missing-raw" else "sources/label.md"
    document = knowledge / document_path
    if problem not in ("missing-source", "missing-raw"):
        document.parent.mkdir(parents=True)
        document.write_text("unrelated" if problem else "Metformin reduces B12.", encoding="utf-8")
    case = load_cases(CASES)[0].model_copy(
        update={"expected_evidence": [ExpectedEvidence(document_path=document_path, contains="B12")]}
    )
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps([case.model_dump()], ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "rag" / "run.py"),
            "--dry-run",
            "--cases",
            str(cases_file),
            "--knowledge",
            str(knowledge),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )

    assert result.returncode == (1 if problem else 0), result.stdout + result.stderr
    if problem:
        assert ("文件裡沒有這句原文" if problem == "wrong-text" else "找不到文件") in result.stdout
    else:
        assert f"{case.id}: ok" in result.stdout
