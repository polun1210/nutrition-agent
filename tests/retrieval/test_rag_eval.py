"""RAG eval 的資料格式與計分（離線）；打真模型的部分在 evals/rag/run.py。"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from nutrition_agent.reference import RuleStatus, load_reference_data
from nutrition_agent.retrieval.evaluation import (
    ExpectedEvidence,
    load_cases,
    missing_raw_corpus,
    score_points,
    score_retrieval,
    validate_against_corpus,
)
from tests.reporting.test_explanation import evidence

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "rag" / "cases.json"
KNOWLEDGE = ROOT / "knowledge"


def _case_expecting(*document_paths: str):
    return load_cases(CASES)[0].model_copy(
        update={
            "expected_evidence": [
                ExpectedEvidence(document_path=path, contains="B12") for path in document_paths
            ]
        }
    )


def test_case_needing_raw_corpus_that_is_not_in_the_repo_gets_a_skip_reason(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "a.md").write_text("B12", encoding="utf-8")
    case = _case_expecting("sources/a.md", "raw/tfda/腸胃用藥/Lansoprazole/x.md")

    reason = missing_raw_corpus(case, tmp_path)

    assert reason is not None
    assert "raw/tfda" in reason


def test_case_is_still_validated_when_raw_corpus_is_present_or_not_needed(tmp_path):
    (tmp_path / "raw" / "tfda").mkdir(parents=True)
    needs_raw = _case_expecting("raw/tfda/腸胃用藥/Lansoprazole/x.md")
    sources_only = _case_expecting("sources/missing.md")

    # 語料在、但缺這份文件：不略過，照樣報錯
    assert missing_raw_corpus(needs_raw, tmp_path) is None
    assert validate_against_corpus(needs_raw, tmp_path)
    assert missing_raw_corpus(sources_only, tmp_path) is None


def test_shipped_cases_load():
    assert len(load_cases(CASES)) >= 3


@pytest.mark.parametrize("case", load_cases(CASES), ids=lambda case: case.id)
def test_shipped_cases_load_and_their_expected_text_exists_in_the_corpus(case):
    # 預期證據在 raw/（TFDA 仿單，不進 git）的題目，只有維護者本機驗得到；其餘照常驗證。
    reason = missing_raw_corpus(case, KNOWLEDGE)
    if reason is not None:
        pytest.skip(reason)

    assert validate_against_corpus(case, KNOWLEDGE) == []


def test_每條審定或草稿規則在非保留題中至少有一題():
    # 草稿也先備題，開發者審定後馬上可以評估；保留題（holdout-）不拿來對規則
    reference = load_reference_data()
    cases = [c for c in load_cases(CASES) if not c.id.startswith("holdout-")]

    def covered(rule) -> bool:
        return any(
            case.ingredient_code == rule.ingredient_code
            and any(
                rule.condition_code in (code, reference.drugs.class_of(code))
                for code in case.drug_ingredient_codes
            )
            for case in cases
        )

    live = [r for r in reference.rules.rules if r.status is not RuleStatus.RETIRED]
    assert [r.id for r in live if not covered(r)] == []


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


def _dry_run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "evals" / "rag" / "run.py"), "--dry-run", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )


def test_dry_run_harness_validates_cases_without_network():
    result = _dry_run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout


def test_dry_run_lists_cases_whose_raw_corpus_is_absent_as_skipped(tmp_path):
    knowledge = tmp_path / "knowledge"
    (knowledge / "sources").mkdir(parents=True)
    (knowledge / "sources" / "a.md").write_text("Metformin reduces B12.", encoding="utf-8")
    cases = [
        _case_expecting("sources/a.md").model_copy(update={"id": "in-git"}),
        _case_expecting("raw/tfda/腸胃用藥/Lansoprazole/x.md").model_copy(update={"id": "needs-raw"}),
    ]
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        json.dumps([case.model_dump() for case in cases], ensure_ascii=False), encoding="utf-8"
    )

    result = _dry_run("--cases", str(cases_file), "--knowledge", str(knowledge))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "in-git: ok" in result.stdout
    assert "needs-raw: 略過：語料不在 repo：raw/tfda" in result.stdout
