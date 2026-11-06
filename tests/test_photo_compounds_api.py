"""照片辨識的化合物（Seam A：HTTP API）：只標化合物重量的列認出所屬營養素，送出後依化合物推估元素量。"""

import json

from tests.test_assessments_api import report_lines
from tests.test_photos_api import JPEG, new_draft, upload


def label_reply(*rows: tuple[str, float, str]) -> str:
    """假 VLM 的標示讀取結果：每列 (標示名稱, 每份含量, 單位)，都在營養標示表裡。"""
    return json.dumps(
        {
            "readable": True,
            "product_name": "鈣片",
            "serving_size": 1,
            "dose_unit": "錠",
            "rows": [
                {"raw_name": name, "section": "nutrition_table", "amount": amount, "unit": unit}
                for name, amount, unit in rows
            ],
        },
        ensure_ascii=False,
    )


def recognized_rows(client) -> dict[str, dict]:
    """上傳一張照片，回傳辨識結果的列（以標示名稱為 key）。"""
    response = upload(client, new_draft(client), JPEG)
    assert response.status_code == 200, response.text
    return {r["raw_name"]: r for r in response.json()["rows"]}


def test_只標化合物重量的列認出所屬營養素與化合物(login_as, gateway):
    gateway.vision_replies = [label_reply(("碳酸鈣", 1250, "mg"))]

    row = recognized_rows(login_as())["碳酸鈣"]

    assert row["ingredient_code"] == "calcium"
    assert row["scope_status"] == "in_scope"
    assert row["compound_code"] == "calcium_carbonate"
    assert row["basis"] == "compound"
    assert row["amount"] == 1250  # 化合物重量照標示保留，元素量由送出時推估


def test_括號裡寫化合物的元素量維持標示載明(login_as, gateway):
    gateway.vision_replies = [label_reply(("鈣（碳酸鈣）", 500, "mg"))]

    row = recognized_rows(login_as())["鈣（碳酸鈣）"]

    assert row["ingredient_code"] == "calcium"
    assert row["basis"] == "labeled"
    assert row["compound_code"] is None


def test_化合物表沒有的化合物維持無法確認(login_as, gateway):
    gateway.vision_replies = [label_reply(("葡萄糖酸鋅", 15, "mg"))]

    row = recognized_rows(login_as())["葡萄糖酸鋅"]

    assert row["ingredient_code"] is None
    assert row["scope_status"] == "unconfirmed"
    assert row["basis"] == "labeled"
    assert row["compound_code"] is None


def test_照片的化合物列送出後依推估元素量做上限比對(login_as, gateway):
    gateway.vision_replies = [label_reply(("碳酸鈣", 1250, "mg"))]
    client = login_as()
    draft_url = new_draft(client)
    recognized = upload(client, draft_url, JPEG).json()
    [row] = recognized["rows"]
    # 校對頁把辨識結果原樣帶進成分行（與手動輸入的成分行結構相同）
    line = {key: row[key] for key in ("ingredient_code", "amount", "unit", "basis", "compound_code")}
    product = {
        "name": "鈣片",
        "dose_unit": "錠",
        "units_per_serving": 1,
        "ingredients": [line],
        "intake": {"frequency": "daily", "times_per_day": 1, "units_per_time": 1},
        "photo_ids": [p["photo_id"] for p in recognized["photos"]],
    }

    assert client.put(draft_url, json={"products": [product]}).status_code == 200
    case_id = client.post(f"{draft_url}/submit").json()["id"]

    calcium = next(
        line for line in report_lines(client, case_id, "ul_comparison") if "鈣" in line and "每日攝取量" in line
    )
    assert "500.5 mg" in calcium  # 碳酸鈣 1250 mg × 鈣比率 0.4004，不是 1250 mg
    assert "此數值為系統推估，非標示值" in calcium
