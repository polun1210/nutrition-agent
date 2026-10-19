"""評估流程（Seam A）：服用頻率、跨產品加總、修改／刪除產品（#6）。"""

from tests.test_assessments_api import report_lines, report_text, submit, supplement


def test_non_daily_product_report_uses_taking_day_wording(login_as):
    client = login_as()
    _, response = submit(client, supplement(frequency="every_other_day"))  # 500 mg 鈣

    lines = report_lines(client, response.json()["id"], "ul_comparison")

    assert any("你服用當日來自補充劑的攝取量已達上限的 20%" in line for line in lines)


def test_daily_only_report_keeps_plain_wording(login_as):
    client = login_as()
    _, response = submit(client, supplement())

    assert "你服用當日" not in report_text(client, response.json()["id"])


def test_two_products_sum_to_exceeded_though_each_is_under(login_as):
    client = login_as()
    calcium = [{"ingredient_code": "calcium", "amount": 1500, "unit": "mg"}]
    _, response = submit(client, supplement("鈣 A", lines=calcium), supplement("鈣 B", lines=calcium))

    lines = report_lines(client, response.json()["id"], "ul_comparison")

    assert any("鈣" in line and "已超過上限" in line for line in lines)


def test_as_needed_frequency_is_rejected_by_the_api(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()

    response = client.put(
        f"/api/assessments/drafts/{draft['id']}",
        json={"products": [supplement(frequency="as_needed")]},
    )

    assert response.status_code == 422


def test_products_can_be_edited_and_deleted_before_submit(login_as):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()
    url = f"/api/assessments/drafts/{draft['id']}"
    client.put(url, json={"products": [supplement("A"), supplement("B")]})

    client.put(url, json={"products": [supplement("A", frequency="weekly_days", days_per_week=3)]})

    products = client.get(url).json()["products"]
    assert [p["name"] for p in products] == ["A"]
    assert products[0]["intake"]["days_per_week"] == 3
