"""評估 API 的白話解釋：送出時產生並凍結，重看報告不會再呼叫模型。"""

import pytest

from nutrition_agent.api.assessments import get_reference
from tests.assessment.conftest import fx_ref, ref  # noqa: F401
from tests.reporting.test_explanation import GOOD, seed_evidence
from tests.test_assessments_api import submit, supplement

B12 = supplement(
    "B12 錠", lines=[{"ingredient_code": "vitamin_b12", "amount": 100, "unit": "ug"}]
)


@pytest.fixture(autouse=True)
def approved_rules(app, fx_ref):  # noqa: F811
    app.dependency_overrides[get_reference] = lambda: fx_ref


def submit_with_metformin(client):
    draft = client.post("/api/assessments/drafts").json()
    client.put(
        f"/api/assessments/drafts/{draft['id']}",
        json={"products": [B12], "medications": [{"name": "Metformin"}]},
    )
    response = client.post(f"/api/assessments/drafts/{draft['id']}/submit")
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_report_carries_explanations_and_clickable_footnotes(login_as, db, gateway):
    seed_evidence(db)
    gateway.complete_reply = GOOD
    client = login_as()

    case = client.get(f"/api/assessments/{submit_with_metformin(client)}").json()

    report = case["report"]
    assert report["explanations"][0]["source"] == "llm"
    assert report["explanations"][0]["sentences"][0]["footnotes"] == [1]
    assert report["footnotes"][0]["source_label"] == "NIH ODS"
    assert "Metformin might reduce" in report["footnotes"][0]["text"]


def test_explanation_is_frozen_and_not_regenerated_on_reopen(login_as, db, gateway):
    seed_evidence(db)
    gateway.complete_reply = GOOD
    client = login_as()
    case_id = submit_with_metformin(client)
    first = client.get(f"/api/assessments/{case_id}").json()["report"]
    calls = len(gateway.calls)

    gateway.complete_reply = "{}"
    second = client.get(f"/api/assessments/{case_id}").json()["report"]

    assert second == first
    assert len(gateway.calls) == calls


def test_report_is_still_complete_when_the_model_misbehaves(login_as, db, gateway):
    seed_evidence(db)
    gateway.complete_reply = "不是 JSON"
    client = login_as()

    case = client.get(f"/api/assessments/{submit_with_metformin(client)}").json()

    assert case["report"]["explanations"][0]["source"] == "template"
    assert case["report"]["footnotes"] == []
    assert [s["key"] for s in case["report"]["sections"]][:3] == [
        "profile",
        "ul_comparison",
        "interaction",
    ]


def test_case_without_interactions_has_no_explanations(login_as, gateway):
    client = login_as()
    _, response = submit(client, supplement())

    report = client.get(f"/api/assessments/{response.json()['id']}").json()["report"]

    assert report["explanations"] == [] and report["footnotes"] == []
    assert not any(kind == "complete" for kind, _ in gateway.calls)
