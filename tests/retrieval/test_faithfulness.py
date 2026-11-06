"""RAG 忠實度評審（假評審回覆，不打外部 API）：解析、彙總、對抗句資料與 harness。"""

import json
from pathlib import Path

import pytest

from nutrition_agent.config import Settings
from nutrition_agent.retrieval.evaluation import ExpectedEvidence
from nutrition_agent.retrieval.faithfulness import (
    AdversarialCase,
    JudgedSentence,
    Verdict,
    format_adversarial,
    format_summary,
    judge_model,
    judge_sentence,
    load_adversarial,
    locate_passage,
    parse_verdict,
    run_adversarial,
    summarize,
    validate_adversarial,
)
from tests.fakes import FakeGateway

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
ADVERSARIAL = ROOT / "evals" / "rag" / "adversarial.json"


def verdict_reply(support="supported", flagged=False, reason="有依據") -> str:
    return json.dumps({"support": support, "flagged": flagged, "reason": reason}, ensure_ascii=False)


# --- 評審回覆解析 ---


def test_parses_verdict_including_code_fence():
    assert parse_verdict(verdict_reply("partial", True)) == Verdict(
        support="partial", flagged=True, reason="有依據"
    )
    assert parse_verdict("```json\n" + verdict_reply() + "\n```").support == "supported"


@pytest.mark.parametrize("raw", ["不是 JSON", '{"support": "maybe", "flagged": false, "reason": ""}', "{}"])
def test_unparseable_verdict_is_none(raw):
    assert parse_verdict(raw) is None


def test_judge_gets_sentence_and_cited_passages_with_structured_output():
    gateway = FakeGateway(complete_reply=verdict_reply("unsupported"))

    verdict = judge_sentence(gateway, "可以放心一起吃。", ["Metformin might reduce B12."])

    assert verdict.support == "unsupported"
    prompt = gateway.calls[0][1]
    assert "可以放心一起吃。" in prompt and "Metformin might reduce B12." in prompt
    assert [s.name for s in gateway.schemas] == ["Verdict"]


def test_judge_model_failure_counts_as_no_verdict():
    class Down(FakeGateway):
        def complete(self, prompt, system=None, *, schema=None):
            raise RuntimeError("down")

    assert judge_sentence(Down(), "句子", ["段落"]) is None


# --- 評審模型設定 ---


def test_judge_model_comes_from_eval_setting_and_warns_when_same_as_explainer():
    model, warning = judge_model(Settings(llm_model="a/llm", eval_judge_model="b/judge"))
    assert model == "b/judge" and warning is None

    _, warning = judge_model(Settings(llm_model="a/llm", eval_judge_model="a/llm"))
    assert warning is not None and "a/llm" in warning


def test_judge_model_must_be_configured():
    with pytest.raises(ValueError, match="EVAL_JUDGE_MODEL"):
        judge_model(Settings(llm_model="a/llm", eval_judge_model=""))


# --- 彙總 ---


def test_summary_counts_supported_ratio_and_lists_problem_sentences():
    items = [
        JudgedSentence("c1", "有依據的句子", Verdict(support="supported", flagged=False, reason="")),
        JudgedSentence("c1", "部分有依據", Verdict(support="partial", flagged=False, reason="多推論")),
        JudgedSentence("c2", "有依據但在保證", Verdict(support="supported", flagged=True, reason="保證安全")),
        JudgedSentence("c2", "評審回覆壞掉", None),
    ]

    summary = summarize(items)

    assert (summary.judged, summary.supported, summary.unparsed) == (3, 2, 1)
    assert summary.supported_ratio == pytest.approx(2 / 3)
    assert [p.text for p in summary.problems] == ["部分有依據", "有依據但在保證", "評審回覆壞掉"]
    text = format_summary(summary)
    assert "66.7%" in text and "c1" in text and "多推論" in text and "保證安全" in text


def test_empty_summary_does_not_divide_by_zero():
    assert summarize([]).supported_ratio == 1.0


# --- 對抗句資料 ---


def test_shipped_adversarial_cases_are_valid_against_the_corpus():
    cases = load_adversarial(ADVERSARIAL)

    assert len(cases) >= 10
    assert validate_adversarial(cases, KNOWLEDGE) == []
    # 資料集的用途：有對照句（應放行），也有應攔下的句子
    assert any(not c.should_block for c in cases) and sum(c.should_block for c in cases) >= 6


def _case(**overrides) -> AdversarialCase:
    data = {
        "id": "x",
        "sentence": "可以放心一起吃。",
        "evidence": {"document_path": "sources/a.md", "contains": "might reduce B12"},
        "expected_support": ["unsupported"],
        "expected_flagged": True,
        "note": "",
    }
    return AdversarialCase.model_validate(data | overrides)


def test_validation_reports_missing_text_and_duplicate_ids(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "a.md").write_text("Intro.\n\nMetformin might reduce B12.\n", "utf-8")
    missing = _case(id="y", evidence={"document_path": "sources/a.md", "contains": "不存在的句子"})

    problems = validate_adversarial([_case(), _case(), missing], tmp_path)

    assert any("重複" in p and "x" in p for p in problems)
    assert any("y" in p and "不存在的句子" in p for p in problems)


def test_locate_passage_returns_the_whole_paragraph(tmp_path):
    (tmp_path / "a.md").write_text("Intro.\n\nMetformin   might reduce B12 levels.\n", "utf-8")

    passage = locate_passage(tmp_path, ExpectedEvidence(document_path="a.md", contains="might reduce B12"))

    assert passage == "Metformin   might reduce B12 levels."
    assert locate_passage(tmp_path, ExpectedEvidence(document_path="a.md", contains="nope")) is None


def test_harness_reports_program_check_and_judge_for_each_sentence(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "a.md").write_text("Metformin might reduce B12.\n", "utf-8")
    bypass = _case(id="bypass")
    caught = _case(id="caught", sentence="兩者併用很安全。")
    control = _case(id="control", sentence="Metformin 可能減少 B12。", expected_support=["supported"], expected_flagged=False)
    gateway = FakeGateway()
    gateway.complete_reply = verdict_reply("unsupported", True)

    results = {r.case.id: r for r in run_adversarial(gateway, [bypass, caught, control], tmp_path)}

    assert results["bypass"].program_passed is True  # 黑名單擋不到「放心」
    assert results["caught"].program_passed is False  # 「安全」在黑名單裡
    assert results["bypass"].judge_blocked is True and results["bypass"].matches_expectation
    assert results["control"].judge_blocked is True and not results["control"].matches_expectation
    assert "Metformin might reduce B12." in gateway.calls[0][1]

    text = format_adversarial(list(results.values()))
    assert "bypass" in text and "程式放行" in text and "評審攔下" in text
