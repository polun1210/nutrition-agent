"""接續未送出的草稿（Seam A：HTTP API）。"""

from datetime import datetime

from tests.test_assessments_api import supplement
from tests.test_medications_api import med

RESUMABLE = "/api/assessments/drafts/resumable"


def new_draft(client, products=(), medications=()):
    draft = client.post("/api/assessments/drafts").json()
    if products or medications:
        save(client, draft["id"], products, medications)
    return draft["id"]


def save(client, draft_id, products=(), medications=()):
    saved = client.put(
        f"/api/assessments/drafts/{draft_id}",
        json={"products": list(products), "medications": list(medications)},
    )
    assert saved.status_code == 200, saved.text


def test_resumable_draft_summarises_counts_and_last_modified_time(login_as):
    client = login_as()
    draft_id = new_draft(client, [supplement("A"), supplement("B")], [med("Amlodipine")])

    response = client.get(RESUMABLE)

    assert response.status_code == 200
    summary = response.json()
    assert summary["id"] == draft_id
    assert summary["product_count"] == 2
    assert summary["medication_count"] == 1
    assert datetime.fromisoformat(summary["updated_at"]).tzinfo is not None


def test_empty_drafts_are_not_resumable(login_as):
    client = login_as()
    new_draft(client)
    cleared = new_draft(client, [supplement()])
    save(client, cleared, [], [])

    assert client.get(RESUMABLE).status_code == 404


def test_submitted_draft_is_not_resumable(login_as):
    client = login_as()
    draft_id = new_draft(client, [supplement()])
    assert client.post(f"/api/assessments/drafts/{draft_id}/submit").status_code == 201

    assert client.get(RESUMABLE).status_code == 404


def test_other_users_drafts_are_never_resumable(login_as):
    a, b = login_as("a@x.com"), login_as("b@x.com")
    b_draft = new_draft(b, [supplement("B 的")])

    assert a.get(RESUMABLE).status_code == 404
    assert b.get(RESUMABLE).json()["id"] == b_draft


def test_resumable_draft_requires_login(client):
    assert client.get(RESUMABLE).status_code == 401


def test_latest_saved_draft_wins(login_as):
    client = login_as()
    new_draft(client, [supplement("先建的")])
    later = new_draft(client, [], [med("Amlodipine")])

    assert client.get(RESUMABLE).json()["id"] == later


def test_older_draft_edited_last_wins_over_newer_one(login_as):
    client = login_as()
    older = new_draft(client, [supplement("A")])
    new_draft(client, [supplement("B")])

    save(client, older, [supplement("A"), supplement("A2")])

    summary = client.get(RESUMABLE).json()
    assert summary["id"] == older
    assert summary["product_count"] == 2


def test_starting_new_or_copying_keeps_the_unfinished_draft(login_as):
    client = login_as()
    finished = new_draft(client, [supplement("上次送出的")])
    client.post(f"/api/assessments/drafts/{finished}/submit")
    unfinished = new_draft(client, [supplement("填到一半")])
    before = client.get(f"/api/assessments/drafts/{unfinished}").json()

    client.post("/api/assessments/drafts")
    assert client.get(RESUMABLE).json()["id"] == unfinished  # 新的空草稿不搶走
    copied = client.post("/api/assessments/drafts?copy_from=latest").json()

    assert client.get(f"/api/assessments/drafts/{unfinished}").json() == before
    assert client.get(RESUMABLE).json()["id"] == copied["id"]
