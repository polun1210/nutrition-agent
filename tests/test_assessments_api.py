"""評估流程（Seam A：HTTP API）：草稿逐步儲存 → 送出成不可變個案 → 報告。"""

from datetime import date


def supplement(name="鈣片", lines=None, **intake):
    return {
        "name": name,
        "dose_unit": "粒",
        "units_per_serving": 2,
        "ingredients": lines or [{"ingredient_code": "calcium", "amount": 500, "unit": "mg"}],
        "intake": {"frequency": "daily", "times_per_day": 1, "units_per_time": 2, **intake},
    }


def submit(client, *products):
    """建立草稿、存入產品、送出；回傳 (draft_id, 送出回應)。"""
    draft = client.post("/api/assessments/drafts").json()
    saved = client.put(f"/api/assessments/drafts/{draft['id']}", json={"products": list(products)})
    assert saved.status_code == 200, saved.text
    return draft["id"], client.post(f"/api/assessments/drafts/{draft['id']}/submit")


def report_lines(client, case_id, section):
    case = client.get(f"/api/assessments/{case_id}").json()
    return next(s for s in case["report"]["sections"] if s["key"] == section)["lines"]


def report_text(client, case_id):
    case = client.get(f"/api/assessments/{case_id}").json()
    return "\n".join(line for s in case["report"]["sections"] for line in s["lines"])


def test_ingredient_menu_lists_display_names_with_unknown_last(login_as):
    options = login_as().get("/api/assessments/ingredient-options").json()

    assert {"code": "calcium", "name": "鈣", "unit": "mg"} in options
    assert any(o["name"] == "輔酶 Q10" for o in options)
    assert options[-1] == {"code": "unknown", "name": "無法確定", "unit": "mg"}


def test_draft_is_saved_step_by_step_and_can_be_replaced(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts")
    assert draft.status_code == 201
    url = f"/api/assessments/drafts/{draft.json()['id']}"
    assert client.get(url).json()["products"] == []

    client.put(url, json={"products": [supplement("A")]})
    client.put(url, json={"products": [supplement("A"), supplement("B")]})

    assert [p["name"] for p in client.get(url).json()["products"]] == ["A", "B"]


def test_submit_freezes_a_case_with_age_versions_and_report(login_as):
    client = login_as()

    _, response = submit(client, supplement())

    assert response.status_code == 201
    case = client.get(f"/api/assessments/{response.json()['id']}").json()
    assert case["age"] == date.today().year - 1950 - (1 if date.today().month < 6 else 0)
    assert case["profile"]["sex"] == "female"
    assert case["products"][0]["name"] == "鈣片"
    assert set(case["reference_versions"]) >= {"dris", "ingredients", "rules"}
    assert [s["key"] for s in case["report"]["sections"]][:2] == ["profile", "ul_comparison"]


def test_report_shows_percent_of_ul_rendered_by_template(login_as):
    client = login_as()
    _, response = submit(client, supplement())  # 每份 2 粒含鈣 500 mg，每次 2 粒 → 500 mg

    lines = report_lines(client, response.json()["id"], "ul_comparison")

    assert any("鈣" in line and "20%" in line for line in lines)
    assert not any("已超過上限" in line for line in lines)


def test_exceeding_the_ul_is_marked_and_no_near_limit_state_exists(login_as):
    client = login_as()
    over = supplement(lines=[{"ingredient_code": "calcium", "amount": 2500, "unit": "mg"}])
    near = supplement("鋅", lines=[{"ingredient_code": "zinc", "amount": 34, "unit": "mg"}])
    _, response = submit(client, over, near)

    lines = report_lines(client, response.json()["id"], "ul_comparison")

    assert any("鈣" in line and "已超過上限" in line for line in lines)
    zinc = next(line for line in lines if "鋅" in line)
    assert "已超過上限" not in zinc and "接近" not in zinc


def test_nutrient_without_ul_and_source_limited_uls_are_labelled(login_as):
    client = login_as()
    lines = [
        {"ingredient_code": "potassium", "amount": 100, "unit": "mg"},
        {"ingredient_code": "magnesium", "amount": 100, "unit": "mg"},
        {"ingredient_code": "iron", "amount": 5, "unit": "mg"},
        {"ingredient_code": "zinc", "amount": 5, "unit": "mg"},
    ]
    _, response = submit(client, supplement(lines=lines))

    out = report_lines(client, response.json()["id"], "ul_comparison")

    assert "無已知上限攝取量" in next(line for line in out if "鉀" in line)
    assert "只計算補充劑來源" in next(line for line in out if "鎂" in line)
    assert "只計算補充劑來源" in next(line for line in out if "鐵" in line)
    assert "只計算補充劑來源" not in next(line for line in out if "鋅" in line)


def test_out_of_scope_ingredient_is_kept_with_neutral_wording(login_as):
    client = login_as()
    q10 = [{"ingredient_code": "coenzyme_q10", "amount": 30, "unit": "mg"}]
    _, response = submit(client, supplement("Q10", lines=q10))

    text = report_text(client, response.json()["id"])

    assert "輔酶 Q10" in text
    assert "不在本系統評估範圍" in text


def test_unconfirmed_ingredient_is_listed_with_pharmacist_warning(login_as):
    client = login_as()
    unknown = [{"ingredient_code": "unknown", "amount": 5, "unit": "mg"}]
    _, response = submit(client, supplement("神秘粉", lines=unknown))

    text = report_text(client, response.json()["id"])

    assert "無法確認" in text and "藥師" in text


def test_report_never_claims_safety(login_as):
    client = login_as(conditions=["hypertension"])
    _, response = submit(client, supplement())

    text = report_text(client, response.json()["id"])

    assert "安全" not in text and "未發現問題" not in text
    assert "你勾選了高血壓" in text


def test_profile_section_describes_choice_of_none_without_claiming_no_disease(login_as):
    client = login_as(conditions=["none"])
    _, response = submit(client, supplement())

    text = report_text(client, response.json()["id"])

    assert "你未勾選本系統涵蓋的 5 種慢性病" in text
    assert "沒有疾病" not in text


def test_editing_profile_later_does_not_change_the_submitted_case(login_as):
    client = login_as()
    _, response = submit(client, supplement())
    case_id = response.json()["id"]
    before = client.get(f"/api/assessments/{case_id}").json()

    client.put(
        "/api/me/profile",
        json={"birth_year": 1990, "birth_month": 1, "sex": "male", "conditions": ["none"]},
    )

    assert client.get(f"/api/assessments/{case_id}").json() == before


def test_under_19_on_assessment_day_cannot_submit(login_as):
    today = date.today()
    client = login_as("kid@example.com", birth_year=today.year - 10, birth_month=1)

    _, response = submit(client, supplement())

    assert response.status_code == 403
    assert "19" in response.json()["detail"]


def test_cannot_submit_without_any_product(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()

    response = client.post(f"/api/assessments/drafts/{draft['id']}/submit")

    assert response.status_code == 422


def test_submitted_draft_is_immutable(login_as):
    client = login_as()
    draft_id, response = submit(client, supplement())
    assert response.status_code == 201

    edit = client.put(f"/api/assessments/drafts/{draft_id}", json={"products": [supplement("B")]})
    again = client.post(f"/api/assessments/drafts/{draft_id}/submit")

    assert edit.status_code == 409
    assert again.status_code == 409


def test_invalid_product_input_is_rejected(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()
    url = f"/api/assessments/drafts/{draft['id']}"
    bad_products = [
        supplement(lines=[{"ingredient_code": "not-a-thing", "amount": 1, "unit": "mg"}]),
        supplement(lines=[{"ingredient_code": "calcium", "amount": -1, "unit": "mg"}]),
        {**supplement(), "dose_unit": "桶"},
        {**supplement(), "units_per_serving": 0},
        supplement(times_per_day=0),
        supplement(frequency="as_needed"),
    ]

    for product in bad_products:
        assert client.put(url, json={"products": [product]}).status_code == 422, product


def test_users_cannot_see_each_others_drafts_or_cases(login_as):
    a = login_as("a@example.com")
    b = login_as("b@example.com")
    draft_id, response = submit(a, supplement())
    open_draft = a.post("/api/assessments/drafts").json()["id"]

    assert b.get(f"/api/assessments/{response.json()['id']}").status_code == 404
    assert b.get(f"/api/assessments/drafts/{open_draft}").status_code == 404
    assert b.put(f"/api/assessments/drafts/{open_draft}", json={"products": []}).status_code == 404
    assert b.post(f"/api/assessments/drafts/{draft_id}/submit").status_code == 404


def test_assessment_endpoints_require_login(client):
    assert client.post("/api/assessments/drafts").status_code == 401
    assert client.get("/api/assessments/1").status_code == 401
