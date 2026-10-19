"""歷史報告與從上一次評估複製（Seam A：HTTP API）。"""

from tests.test_assessments_api import supplement
from tests.test_medications_api import med

LIST = "/api/assessments"


def submit_case(client, products, medications=()):
    draft = client.post("/api/assessments/drafts").json()
    saved = client.put(
        f"/api/assessments/drafts/{draft['id']}",
        json={"products": products, "medications": list(medications)},
    )
    assert saved.status_code == 200, saved.text
    response = client.post(f"/api/assessments/drafts/{draft['id']}/submit")
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_history_lists_only_own_cases_newest_first_with_counts_and_versions(login_as):
    a, b = login_as("a@x.com"), login_as("b@x.com")
    first = submit_case(a, [supplement("A1")])
    second = submit_case(a, [supplement("A2"), supplement("A3")], [med("Amlodipine")])
    submit_case(b, [supplement("B1")])

    items = a.get(LIST).json()

    assert [i["id"] for i in items] == [second, first]
    assert items[0]["product_count"] == 2
    assert items[0]["medication_count"] == 1
    assert items[1]["product_count"] == 1
    assert {"dris", "ingredients", "rules"} <= set(items[0]["reference_versions"])
    assert items[0]["created_at"] and items[0]["assessed_on"]
    assert len(b.get(LIST).json()) == 1


def test_history_requires_login(client):
    assert client.get(LIST).status_code == 401


def test_old_report_is_unchanged_after_profile_and_reference_change(login_as, app):
    from nutrition_agent.api.assessments import get_reference
    from nutrition_agent.reference import load_reference_data

    client = login_as()
    case_id = submit_case(client, [supplement()])
    before = client.get(f"/api/assessments/{case_id}").json()

    client.put(
        "/api/me/profile",
        json={"birth_year": 1990, "birth_month": 1, "sex": "male", "conditions": ["none"]},
    )
    changed = load_reference_data()
    changed.versions["dris"] = "2099-changed"
    app.dependency_overrides[get_reference] = lambda: changed

    after = client.get(f"/api/assessments/{case_id}").json()

    assert after == before
    assert after["reference_versions"]["dris"] != "2099-changed"


COPY = "/api/assessments/drafts?copy_from=latest"


def test_copy_from_latest_brings_products_and_medications_into_a_new_draft(login_as):
    client = login_as()
    submit_case(client, [supplement("舊的")])
    latest = submit_case(
        client,
        [supplement("鈣片", lines=[{"ingredient_code": "calcium", "amount": 300, "unit": "mg"}])],
        [med("Amlodipine")],
    )

    response = client.post(COPY)

    assert response.status_code == 201
    draft = response.json()
    assert draft["submitted_case_id"] is None
    assert draft["products"] == client.get(f"/api/assessments/{latest}").json()["products"]
    assert draft["medications"] == [{"name": "Amlodipine"}]
    assert client.get(f"/api/assessments/drafts/{draft['id']}").json() == draft


def test_copied_draft_can_be_edited_without_touching_the_old_case(login_as):
    client = login_as()
    old = submit_case(client, [supplement("鈣片")], [med("Amlodipine")])
    before = client.get(f"/api/assessments/{old}").json()
    draft = client.post(COPY).json()

    saved = client.put(
        f"/api/assessments/drafts/{draft['id']}",
        json={"products": [supplement("新的")], "medications": []},
    )
    submit = client.post(f"/api/assessments/drafts/{draft['id']}/submit")

    assert saved.status_code == 200 and submit.status_code == 201
    assert client.get(f"/api/assessments/{old}").json() == before
    assert len(client.get(LIST).json()) == 2


def test_copy_uses_current_profile_not_the_old_one(login_as):
    client = login_as()
    submit_case(client, [supplement()])
    client.put(
        "/api/me/profile",
        json={"birth_year": 1960, "birth_month": 1, "sex": "male", "conditions": ["none"]},
    )
    draft = client.post(COPY).json()

    case_id = client.post(f"/api/assessments/drafts/{draft['id']}/submit").json()["id"]

    assert client.get(f"/api/assessments/{case_id}").json()["profile"]["sex"] == "male"


def test_copy_without_history_is_rejected_and_never_uses_other_users_cases(login_as):
    a, b = login_as("a@x.com"), login_as("b@x.com")
    submit_case(a, [supplement("A 的")])

    response = b.post(COPY)

    assert response.status_code == 404
    assert b.post("/api/assessments/drafts").json()["products"] == []
