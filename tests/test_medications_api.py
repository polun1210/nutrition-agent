"""用藥步驟（Seam A：HTTP API）：藥名搜尋、草稿存入用藥、送出時後端重新對照。"""

from tests.test_assessments_api import report_lines, supplement

SEARCH = "/api/assessments/drug-search"


def search(client, q):
    response = client.get(SEARCH, params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


def med(name, **extra):
    return {"name": name, **extra}


def save(client, draft_id, medications, products=None):
    return client.put(
        f"/api/assessments/drafts/{draft_id}",
        json={"products": products or [supplement()], "medications": medications},
    )


def submit_case(client, medications):
    draft = client.post("/api/assessments/drafts").json()
    saved = save(client, draft["id"], medications)
    assert saved.status_code == 200, saved.text
    response = client.post(f"/api/assessments/drafts/{draft['id']}/submit")
    assert response.status_code == 201, response.text
    return response.json()["id"]


def profile_text(client, case_id):
    return "\n".join(report_lines(client, case_id, "profile"))


def test_partial_search_returns_candidates_with_names_and_scope(login_as):
    candidates = search(login_as(), "amlo")

    by_name = {c["name"]: c for c in candidates}
    amlodipine = by_name["Amlodipine"]
    assert amlodipine["scope_status"] == "in_scope"
    assert amlodipine["ingredients"][0]["code"] == "amlodipine"
    assert amlodipine["ingredients"][0]["name_en"] == "Amlodipine"
    assert amlodipine["ingredients"][0]["name_zh"] == "氨氯地平"
    assert amlodipine["ingredients"][0]["class_code"] == "ccb"
    assert "脈優" in amlodipine["brand_names"]


def test_compound_drug_maps_each_ingredient_to_its_own_class(login_as):
    candidates = {c["name"]: c for c in search(login_as(), "雅脈")}

    parts = [(i["code"], i["class_code"]) for i in candidates["雅脈複方錠"]["ingredients"]]
    assert parts == [("amlodipine", "ccb"), ("valsartan", "acei_arb")]


def test_search_marks_out_of_scope_and_banned_ingredients(login_as):
    client = login_as()

    bisoprolol = search(client, "康肯")[0]
    ranitidine = search(client, "zantac")[0]

    assert bisoprolol["scope_status"] == "out_of_scope"
    assert bisoprolol["ingredients"] == []
    assert ranitidine["scope_status"] == "out_of_scope"  # 已下架成分不進範圍


def test_search_does_not_filter_by_known_conditions(login_as):
    healthy = login_as("h@x.com", conditions=["none"])
    diabetic = login_as("d@x.com", conditions=["type2_diabetes"])

    assert search(healthy, "atorva") == search(diabetic, "atorva")
    assert search(diabetic, "atorva")  # 糖尿病患者搜降血脂藥一樣有候選


def test_search_requires_login_and_ignores_blank_query(login_as, client):
    assert client.get(SEARCH, params={"q": "a"}).status_code == 401
    assert search(login_as(), "  ") == []


def test_submit_resolves_names_on_the_backend_and_ignores_client_mapping(login_as):
    client = login_as()
    forged = med(
        "Norvasc",
        scope_status="unconfirmed",
        ingredients=[
            {
                "code": "metformin",
                "name_en": "X",
                "name_zh": "X",
                "class_code": "biguanide",
                "class_name_zh": "X",
            }
        ],
    )

    case_id = submit_case(client, [forged])

    case = client.get(f"/api/assessments/{case_id}").json()
    [medication] = case["medications"]
    assert medication["raw_name"] == "Norvasc"
    assert medication["scope_status"] == "in_scope"
    assert [i["code"] for i in medication["ingredients"]] == ["amlodipine"]


def test_report_lists_each_medication_with_scope_wording(login_as):
    client = login_as()

    case_id = submit_case(
        client, [med("Norvasc"), med("康肯"), med("某個查不到的藥"), med("雅脈複方錠")]
    )

    text = profile_text(client, case_id)
    assert "Norvasc" in text and "氨氯地平" in text and "Amlodipine" in text
    assert "Amlodipine、Valsartan" in text  # 複方列出全部有效成分
    assert "康肯：不在本系統評估範圍" in text
    assert "某個查不到的藥：無法判斷是否有交互作用" in text
    assert "你沒有提供用藥資料" not in text


def test_skipping_medication_is_reported(login_as):
    client = login_as()

    case_id = submit_case(client, [])

    assert "你沒有提供用藥資料" in report_lines(client, case_id, "profile")


def test_deregistered_brand_name_is_unconfirmed(login_as):
    client = login_as()

    case_id = submit_case(client, [med("舊胃藥錠")])  # 已註銷的品名不在藥名表

    assert "舊胃藥錠：無法判斷是否有交互作用" in profile_text(client, case_id)


def test_medication_can_be_removed_and_is_saved_with_draft(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()

    save(client, draft["id"], [med("Norvasc"), med("Lipitor")])
    saved = save(client, draft["id"], [med("Lipitor")]).json()

    assert saved["medications"] == [{"name": "Lipitor"}]


def test_blank_medication_name_is_rejected(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()

    assert save(client, draft["id"], [med("  ")]).status_code == 422
