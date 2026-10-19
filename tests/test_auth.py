from datetime import date

from tests.conftest import register_payload

PASSWORD = "correct-horse-battery"


def test_register_logs_the_user_in_and_returns_profile(client):
    response = client.post("/api/auth/register", json=register_payload())

    assert response.status_code == 201
    me = client.get("/api/me").json()
    assert me["email"] == "a@example.com"
    assert me["profile"] == {
        "birth_year": 1950,
        "birth_month": 6,
        "sex": "female",
        "conditions": ["hypertension"],
    }
    assert "password" not in response.text and "password_hash" not in response.text


def test_register_accepts_none_of_the_above(client):
    response = client.post("/api/auth/register", json=register_payload(conditions=["none"]))

    assert response.status_code == 201


def test_register_rejects_incomplete_or_invalid_profile(client):
    bad_payloads = [
        register_payload(conditions=[]),
        register_payload(conditions=["none", "hypertension"]),
        register_payload(conditions=["cancer"]),
        register_payload(sex="other"),
        register_payload(birth_month=13),
        register_payload(birth_year=2999),
        register_payload(password="short"),
        register_payload(email="not-an-email"),
    ]
    for payload in bad_payloads:
        assert client.post("/api/auth/register", json=payload).status_code == 422, payload
    for missing in ("birth_year", "birth_month", "sex", "conditions"):
        payload = register_payload()
        del payload[missing]
        assert client.post("/api/auth/register", json=payload).status_code == 422, missing


def test_register_rejects_duplicate_email_ignoring_case(client, make_client):
    client.post("/api/auth/register", json=register_payload("a@example.com"))

    other = make_client().post("/api/auth/register", json=register_payload("A@Example.com"))

    assert other.status_code == 409


def test_protected_endpoints_reject_anonymous_requests(client):
    assert client.get("/api/me").status_code == 401
    assert client.put("/api/me/profile", json=register_payload()).status_code == 401


def test_login_and_logout(client, login_as, make_client):
    login_as("a@example.com")
    fresh = make_client()

    wrong = fresh.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    assert wrong.status_code == 401
    ok = fresh.post("/api/auth/login", json={"email": "A@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert fresh.get("/api/me").status_code == 200

    assert fresh.post("/api/auth/logout").status_code == 204
    assert fresh.get("/api/me").status_code == 401


def test_login_does_not_reveal_whether_email_exists(client, login_as):
    login_as("a@example.com")

    unknown = client.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever-123"})
    wrong = client.post("/api/auth/login", json={"email": "a@example.com", "password": "whatever-123"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_user_can_update_own_profile(login_as):
    user = login_as()
    new_profile = {
        "birth_year": 1948,
        "birth_month": 2,
        "sex": "male",
        "conditions": ["type2_diabetes", "hypertension"],
    }

    response = user.put("/api/me/profile", json=new_profile)

    assert response.status_code == 200
    assert user.get("/api/me").json()["profile"] == new_profile


def test_profile_update_applies_same_validation(login_as):
    user = login_as()

    response = user.put(
        "/api/me/profile",
        json={"birth_year": 1948, "birth_month": 2, "sex": "male", "conditions": ["none", "hypertension"]},
    )

    assert response.status_code == 422
    assert user.get("/api/me").json()["profile"]["conditions"] == ["hypertension"]


def test_user_a_cannot_see_or_change_user_b(login_as):
    user_a = login_as("a@example.com")
    user_b = login_as("b@example.com", sex="male", conditions=["none"])

    assert user_a.get("/api/me").json()["email"] == "a@example.com"
    assert user_b.get("/api/me").json()["email"] == "b@example.com"
    user_b.put(
        "/api/me/profile",
        json={"birth_year": 1940, "birth_month": 1, "sex": "male", "conditions": ["none"]},
    )
    assert user_a.get("/api/me").json()["profile"]["birth_year"] == 1950


def test_me_reports_age_for_adult(login_as):
    user = login_as(birth_year=2000, birth_month=1)

    me = user.get("/api/me").json()

    assert me["age"] >= 25
    assert me["is_adult"] is True
    assert me["underage_message"] is None


def test_underage_user_gets_explicit_message(login_as):
    user = login_as("kid@example.com", birth_year=date.today().year - 10, birth_month=1)

    me = user.get("/api/me").json()

    assert me["is_adult"] is False
    assert "未滿 19 歲" in me["underage_message"]
