"""元素量推估（Seam A：HTTP API）：化合物選單、報告註記、無法判定揭露、輸入驗證。"""

from tests.test_assessments_api import report_lines, report_text, submit, supplement


def compound_product(code="calcium", compound="calcium_citrate_tetrahydrate", amount=1000):
    line = {
        "ingredient_code": code,
        "amount": amount,
        "unit": "mg",
        "basis": "compound",
        "compound_code": compound,
    }
    return supplement(lines=[line], units_per_time=2)  # 每份 2 粒、每次 2 粒 = 1 份


def test_compound_menu_lists_ratios_for_the_form_preview(login_as):
    options = login_as().get("/api/assessments/compound-options").json()

    citrate = next(o for o in options if o["code"] == "calcium_citrate_tetrahydrate")
    assert citrate["nutrient_code"] == "calcium"
    assert citrate["name"] == "檸檬酸鈣"
    assert citrate["element_ratio"] == 0.2108
    assert {o["nutrient_code"] for o in options} == {"calcium", "magnesium", "iron"}


def test_estimated_value_is_labelled_in_the_report(login_as):
    client = login_as()
    _, response = submit(client, compound_product())

    out = report_lines(client, response.json()["id"], "ul_comparison")

    calcium = next(line for line in out if "鈣" in line and "每日攝取量" in line)
    assert "210.8" in calcium
    assert "此數值為系統推估，非標示值" in calcium


def test_labeled_value_has_no_estimate_note(login_as):
    client = login_as()
    _, response = submit(client, supplement())

    assert "系統推估" not in report_text(client, response.json()["id"])


def test_undetermined_nutrient_is_disclosed_and_not_totalled(login_as):
    client = login_as()
    zinc = {"ingredient_code": "zinc", "amount": 50, "unit": "mg", "basis": "compound"}
    _, response = submit(client, supplement(lines=[zinc]))

    out = report_lines(client, response.json()["id"], "ul_comparison")

    assert any("鋅" in line and "無法判定" in line for line in out)
    assert not any("鋅" in line and "每日攝取量" in line for line in out)


def test_compound_must_belong_to_the_chosen_nutrient_and_exist(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()
    url = f"/api/assessments/drafts/{draft['id']}"

    for bad in (
        compound_product(compound="magnesium_oxide"),
        compound_product(compound="no_such_compound"),
    ):
        assert client.put(url, json={"products": [bad]}).status_code == 422
