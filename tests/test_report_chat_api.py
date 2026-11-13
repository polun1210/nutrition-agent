"""報告問答（Seam：POST /api/assessments/{id}/chat）。聊天模型換成假的，agent 迴圈與工具是真的。"""

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from nutrition_agent.api.assessments import get_reference
from tests.assessment.conftest import fx_ref, ref  # noqa: F401
from nutrition_agent.report_chat.agent import answer_question
from tests.fakes import FakeChatModel, tool_call
from tests.reporting.test_explanation import seed_evidence
from tests.test_assessments_api import submit, supplement
from tests.test_explanation_api import submit_with_metformin


@pytest.fixture(autouse=True)
def approved_rules(app, fx_ref):  # noqa: F811
    app.dependency_overrides[get_reference] = lambda: fx_ref


def ask(client, case_id, question="為什麼要告知醫師？", history=None):
    return client.post(
        f"/api/assessments/{case_id}/chat",
        json={"question": question, "history": history or []},
    )


def tool_results(model: FakeChatModel) -> list[str]:
    return [m.content for m in model.received[-1] if isinstance(m, ToolMessage)]


def test_agent_reads_the_case_findings_then_answers(login_as, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [tool_call("get_findings"), AIMessage(content="因為 Metformin 會影響 B12。")]

    response = ask(client, case_id)

    assert response.status_code == 200, response.text
    assert response.json() == {"answer": "因為 Metformin 會影響 B12。", "sources": []}
    (findings,) = tool_results(chat_model)
    assert "Metformin" in findings
    assert "維生素 B12" in findings
    assert "告知你的醫師或藥師" in findings


def test_findings_carry_the_ul_percentage_from_the_report(login_as, chat_model):
    client = login_as()
    _, submitted = submit(client, supplement())
    case_id = submitted.json()["id"]
    sections = client.get(f"/api/assessments/{case_id}").json()["report"]["sections"]
    table = next(s for s in sections if s["key"] == "ul_comparison")["table"]
    chat_model.script = [tool_call("get_findings"), AIMessage(content="好")]

    ask(client, case_id)

    (findings,) = tool_results(chat_model)
    assert table[0]["percent"] and table[0]["percent"] in findings


def test_requires_login(client):
    assert ask(client, 1).status_code == 401


def test_other_users_and_missing_cases_are_not_found(login_as, chat_model):
    owner = login_as("owner@example.com")
    case_id = submit_with_metformin(owner)
    stranger = login_as("stranger@example.com")

    assert ask(stranger, case_id).status_code == 404
    assert ask(owner, case_id + 999).status_code == 404
    assert chat_model.received == []


@pytest.mark.parametrize("question", ["", "   \n", "問" * 501])
def test_blank_or_too_long_question_is_rejected(login_as, chat_model, question):
    client = login_as()
    case_id = submit_with_metformin(client)

    assert ask(client, case_id, question).status_code == 422
    assert chat_model.received == []


def test_question_of_exactly_500_chars_is_accepted(login_as, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [AIMessage(content="好")]

    assert ask(client, case_id, "問" * 500).status_code == 200


def test_model_only_receives_the_last_three_turns_of_history(login_as, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    history = [
        {"role": role, "content": f"{role}-{turn}"}
        for turn in range(1, 5)
        for role in ("user", "assistant")
    ]
    chat_model.script = [AIMessage(content="好")]

    ask(client, case_id, "最新的問題", history)

    contents = [m.content for m in chat_model.received[0] if m.type in ("human", "ai")]
    assert contents == [
        "user-2",
        "assistant-2",
        "user-3",
        "assistant-3",
        "user-4",
        "assistant-4",
        "最新的問題",
    ]


def test_model_failure_returns_502_with_friendly_message(login_as, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [RuntimeError("upstream timeout")]

    response = ask(client, case_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "問答服務暫時無法使用，請稍後再試"


def search(call_id="call-1", **args):
    return tool_call("search_evidence", call_id, ingredient_code="vitamin_b12", **args)


def test_search_evidence_feeds_chunk_text_to_model_and_lists_sources(login_as, db, chat_model):
    seed_evidence(db)
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [
        search(drug_ingredient_codes=["metformin"]),
        AIMessage(content="依 NIH ODS，Metformin 會降低吸收。"),
    ]

    response = ask(client, case_id)

    assert response.status_code == 200, response.text
    (result,) = tool_results(chat_model)
    assert "Metformin might reduce the absorption of vitamin B12." in result
    assert response.json()["sources"] == [
        {
            "source_label": "NIH ODS",
            "document_name": "VitaminB12-HealthProfessional.md",
            "section": "Interactions with Medications",
            "text": "Metformin might reduce the absorption of vitamin B12.",
        }
    ]


def test_same_chunk_retrieved_twice_appears_once_in_sources(login_as, db, chat_model):
    seed_evidence(db)
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [search("call-1"), search("call-2"), AIMessage(content="好")]

    assert len(ask(client, case_id).json()["sources"]) == 1


def test_sources_are_empty_when_search_was_not_called(login_as, db, chat_model):
    seed_evidence(db)
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [tool_call("get_findings"), AIMessage(content="好")]

    assert ask(client, case_id).json()["sources"] == []


def test_findings_list_the_codes_the_model_may_search(login_as, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    chat_model.script = [tool_call("get_findings"), AIMessage(content="好")]

    ask(client, case_id)

    (findings,) = tool_results(chat_model)
    assert '"vitamin_b12"' in findings and '"metformin"' in findings


def test_answer_reports_tool_calls_in_order(login_as, db, chat_model):
    client = login_as()
    case_id = submit_with_metformin(client)
    report, assessment = db.execute(
        "SELECT report, assessment FROM assessment_cases WHERE id = %s", (case_id,)
    ).fetchone()
    chat_model.script = [
        tool_call("get_findings", "call-1"),
        search("call-2", drug_ingredient_codes=["metformin"]),
        AIMessage(content="好"),
    ]

    result = answer_question(chat_model, report, assessment, "問", [], lambda code, drugs: [])

    assert result.answer == "好"
    assert [(c.name, c.args) for c in result.tool_calls] == [
        ("get_findings", {}),
        ("search_evidence", {"ingredient_code": "vitamin_b12", "drug_ingredient_codes": ["metformin"]}),
    ]
