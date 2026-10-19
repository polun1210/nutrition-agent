"""白話解釋（Seam C：模型閘道用假回應）：輸出檢查、重試、退回審定說明文字。"""

import json

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.explanation import (
    MAX_RETRIES,
    build_explanations,
    check_sentences,
    explain_finding,
)
from nutrition_agent.retrieval.search import Evidence
from tests.assessment.conftest import drug, line, make_case, product

METFORMIN = drug("Glucophage", ("metformin", "biguanide"))
B12 = product("B12 錠", [line("vitamin_b12", 100, "ug")])


def evidence(ev_id: str = "ev-aaa", source_type: str = "nih_ods_health_professional") -> Evidence:
    return Evidence(
        id=ev_id,
        source_type=source_type,
        document_name="VitaminB12-HealthProfessional.md",
        document_path="sources/nih_ods/VitaminB12-HealthProfessional.md",
        ingredients=("vitamin_b12", "metformin"),
        section="Interactions with Medications",
        start_line=1,
        end_line=2,
        text="Metformin might reduce the absorption of vitamin B12.",
        similarity=0.9,
    )


def reply(*sentences: tuple[str, list[str]]) -> str:
    return json.dumps(
        [{"text": t, "evidence_ids": ids} for t, ids in sentences], ensure_ascii=False
    )


GOOD = reply(("這個藥可能影響維生素 B12 的吸收。", ["ev-aaa"]))


class ScriptedGateway:
    """依序回覆；用完後重複最後一則。embed 回傳固定向量。"""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, prompt, system=None):
        self.prompts.append(prompt)
        item = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(item, Exception):
            raise item
        return item

    def embed(self, texts):
        return [[0.0] * 4 for _ in texts]

    def vision(self, prompt, image, mime_type):  # pragma: no cover
        raise NotImplementedError


def finding(fx_ref):
    case = make_case(B12, medications=(METFORMIN,))
    return assess(case, fx_ref).interactions[0], case


# --- 輸出檢查（純程式） ---


def test_clean_sentences_pass():
    assert check_sentences([("可能影響維生素 B12 的吸收。", ["ev-aaa"])], {"ev-aaa"}) == []


def test_any_quantity_digit_fails_but_names_with_digits_do_not():
    assert check_sentences([("每天 2 次。", ["ev-aaa"])], {"ev-aaa"})
    ok = [("影響維生素 B12 與 n-3 脂肪酸、輔酶 Q10。", ["ev-aaa"])]
    assert check_sentences(ok, {"ev-aaa"}) == []


def test_sentence_without_evidence_id_fails():
    assert check_sentences([("可能影響吸收。", [])], {"ev-aaa"})


def test_cited_id_outside_retrieved_results_fails():
    assert check_sentences([("可能影響吸收。", ["ev-zzz"])], {"ev-aaa"})


def test_forbidden_words_fail():
    for word in ("安全", "未發現問題", "確診", "劑量", "停用", "購買"):
        assert check_sentences([(f"這是{word}的。", ["ev-aaa"])], {"ev-aaa"}), word


def test_empty_explanation_fails():
    assert check_sentences([], {"ev-aaa"})


# --- 產生、重試、退回 ---


def test_valid_reply_is_accepted_with_one_call(fx_ref):
    f, _ = finding(fx_ref)
    gw = ScriptedGateway(GOOD)

    sentences = explain_finding(gw, f, "維生素 B12", [evidence()])

    assert [s.text for s in sentences] == ["這個藥可能影響維生素 B12 的吸收。"]
    assert sentences[0].evidence_ids == ["ev-aaa"]
    assert len(gw.prompts) == 1
    assert "ev-aaa" in gw.prompts[0] and "Glucophage" in gw.prompts[0]


def test_invalid_then_valid_reply_retries(fx_ref):
    f, _ = finding(fx_ref)
    gw = ScriptedGateway(reply(("每天 2 次。", ["ev-aaa"])), GOOD)

    sentences = explain_finding(gw, f, "維生素 B12", [evidence()])

    assert sentences is not None and len(gw.prompts) == 2


def test_gives_up_after_max_retries(fx_ref):
    f, _ = finding(fx_ref)
    gw = ScriptedGateway(reply(("沒有引用。", [])))

    assert explain_finding(gw, f, "維生素 B12", [evidence()]) is None
    assert len(gw.prompts) == 1 + MAX_RETRIES == 3


def test_unparseable_or_failing_model_counts_as_invalid(fx_ref):
    f, _ = finding(fx_ref)

    assert explain_finding(ScriptedGateway("不是 JSON"), f, "維生素 B12", [evidence()]) is None
    down = ScriptedGateway(RuntimeError("down"))
    assert explain_finding(down, f, "維生素 B12", [evidence()]) is None


def test_no_evidence_means_no_model_call(fx_ref):
    f, _ = finding(fx_ref)
    gw = ScriptedGateway(GOOD)

    assert explain_finding(gw, f, "維生素 B12", []) is None
    assert gw.prompts == []


# --- 整份報告：腳註與退回 ---


def seed_evidence(db, ev_id="ev-aaa"):
    db.execute(
        "INSERT INTO evidence_chunk (id, source_type, document_name, document_path, ingredients,"
        " section, start_char, end_char, start_line, end_line, text, embedding)"
        " VALUES (%s,%s,%s,%s,%s,%s,0,10,%s,%s,%s,%s::vector)",
        (
            ev_id,
            "nih_ods_health_professional",
            "VitaminB12-HealthProfessional.md",
            "sources/nih_ods/VitaminB12-HealthProfessional.md",
            ["vitamin_b12", "metformin"],
            "Interactions with Medications",
            1,
            2,
            "Metformin might reduce the absorption of vitamin B12.",
            "[0,0,0,0]",
        ),
    )


def test_build_explanations_numbers_footnotes_with_source_and_text(db, fx_ref):
    seed_evidence(db)
    assessment = assess(make_case(B12, medications=(METFORMIN,)), fx_ref)

    explanations, footnotes = build_explanations(db, ScriptedGateway(GOOD), assessment, fx_ref)

    assert [e.source for e in explanations] == ["llm"]
    assert explanations[0].ingredient_code == "vitamin_b12"
    assert explanations[0].sentences[0].footnotes == [1]
    assert footnotes[0].number == 1
    assert footnotes[0].source_label == "NIH ODS"
    assert footnotes[0].text.startswith("Metformin might reduce")
    assert footnotes[0].document_name == "VitaminB12-HealthProfessional.md"


def test_build_explanations_falls_back_to_approved_reason_text(db, fx_ref):
    seed_evidence(db)
    assessment = assess(make_case(B12, medications=(METFORMIN,)), fx_ref)

    explanations, footnotes = build_explanations(
        db, ScriptedGateway(reply(("有數字 3。", ["ev-aaa"]))), assessment, fx_ref
    )

    assert explanations[0].source == "template"
    assert [s.text for s in explanations[0].sentences] == list(
        assessment.interactions[0].reasons_zh
    )
    assert footnotes == []


def test_build_explanations_survives_retrieval_failure(db, fx_ref):
    class BrokenEmbed(ScriptedGateway):
        def embed(self, texts):
            raise RuntimeError("embedding down")

    assessment = assess(make_case(B12, medications=(METFORMIN,)), fx_ref)
    explanations, _ = build_explanations(db, BrokenEmbed(GOOD), assessment, fx_ref)

    assert explanations[0].source == "template"
