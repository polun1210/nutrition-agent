"""保健食品照片：上傳 → 辨識（假模型閘道）→ 預填；照片只有本人拿得到。"""

import json
from pathlib import Path

import httpx

from tests.test_assessments_api import supplement

RECORDED = Path(__file__).resolve().parents[1] / "evals" / "vlm" / "recorded" / "vlm"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
UNREADABLE = json.dumps({"readable": False, "rows": []})
BACK = json.dumps(
    {
        "readable": True,
        "rows": [{"raw_name": "鎂", "section": "nutrition_table", "amount": 100, "unit": "mg"}],
    }
)


def p01_reply() -> str:
    return (RECORDED / "p01-img01.json").read_text(encoding="utf-8")


def new_draft(client) -> str:
    return f"/api/assessments/drafts/{client.post('/api/assessments/drafts').json()['id']}"


def upload(client, draft_url, *images, **data):
    files = [("files", (f"p{i}.jpg", image, "image/jpeg")) for i, image in enumerate(images)]
    return client.post(f"{draft_url}/photos", files=files, data=data)


def test_多張照片合併成一筆並預填(login_as, gateway):
    gateway.vision_replies = [p01_reply(), BACK]
    client = login_as()

    response = upload(client, new_draft(client), JPEG, PNG)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_name"] == "挺立 葡萄糖胺強力錠"
    assert body["units_per_serving"] == 3 and body["dose_unit"] == "錠"
    assert {r["raw_name"] for r in body["rows"]} >= {"鈣", "鎂"}
    assert [p["readable"] for p in body["photos"]] == [True, True]
    assert len(gateway.calls) == 2


def test_讀不到的照片會指出是哪一張並附重拍提示(login_as, gateway):
    gateway.vision_replies = [p01_reply(), UNREADABLE]
    client = login_as()

    body = upload(client, new_draft(client), JPEG, PNG).json()

    first, second = body["photos"]
    assert first["readable"] is True
    assert second["readable"] is False and "重拍" in second["hint"]
    assert body["rows"]  # 讀得到的那張照樣預填


def test_已辨識過的照片用編號補進來不會重新辨識(login_as, gateway):
    gateway.vision_replies = [UNREADABLE, BACK]
    client = login_as()
    draft_url = new_draft(client)
    first = upload(client, draft_url, JPEG).json()
    bad_id = first["photos"][0]["photo_id"]

    second = upload(client, draft_url, PNG, photo_ids=[bad_id]).json()

    assert len(gateway.calls) == 2  # 第一次一張、第二次只有新的一張
    assert [p["photo_id"] for p in second["photos"]][0] == bad_id
    assert {r["raw_name"] for r in second["rows"]} == {"鎂"}


def test_照片只有本人拿得到(login_as, make_client, gateway):
    gateway.vision_replies = [p01_reply()]
    owner = login_as("a@example.com")
    other = login_as("b@example.com")
    photo_id = upload(owner, new_draft(owner), JPEG).json()["photos"][0]["photo_id"]

    mine = owner.get(f"/api/photos/{photo_id}")
    assert mine.status_code == 200
    assert mine.content == JPEG and mine.headers["content-type"] == "image/jpeg"
    assert other.get(f"/api/photos/{photo_id}").status_code == 404
    assert make_client().get(f"/api/photos/{photo_id}").status_code == 401


def test_不能把別人的草稿或照片拿來用(login_as, gateway):
    gateway.vision_replies = [p01_reply()]
    owner = login_as("a@example.com")
    other = login_as("b@example.com")
    owner_draft = new_draft(owner)
    photo_id = upload(owner, owner_draft, JPEG).json()["photos"][0]["photo_id"]

    assert upload(other, owner_draft, JPEG).status_code == 404
    assert upload(other, new_draft(other), PNG, photo_ids=[photo_id]).status_code == 404


def test_只收圖片檔(login_as, gateway):
    client = login_as()
    draft_url = new_draft(client)

    assert upload(client, draft_url, b"%PDF-1.4 not an image").status_code == 422
    assert upload(client, draft_url).status_code == 422  # 沒附任何照片
    assert gateway.calls == []


def test_模型服務故障時回報稍後再試且不留下照片(login_as, gateway, db):
    gateway.vision_replies = [httpx.ConnectError("boom")]
    client = login_as()

    response = upload(client, new_draft(client), JPEG)

    assert response.status_code == 502
    assert db.execute("SELECT count(*) FROM product_photos").fetchone()[0] == 0


def test_已送出的草稿不能再上傳(login_as, gateway):
    client = login_as()
    draft_url = new_draft(client)
    client.put(draft_url, json={"products": [supplement()]})
    client.post(f"{draft_url}/submit")

    assert upload(client, draft_url, JPEG).status_code == 409


def test_產品掛上自己的照片並凍結進評估個案(login_as, gateway):
    gateway.vision_replies = [p01_reply()]
    client = login_as()
    draft_url = new_draft(client)
    photo_id = upload(client, draft_url, JPEG).json()["photos"][0]["photo_id"]

    saved = client.put(draft_url, json={"products": [{**supplement("鈣片"), "photo_ids": [photo_id]}]})
    assert saved.status_code == 200, saved.text
    case_id = client.post(f"{draft_url}/submit").json()["id"]

    case = client.get(f"/api/assessments/{case_id}").json()
    assert case["products"][0]["photo_ids"] == [photo_id]


def test_產品不能掛別人的照片(login_as, gateway):
    gateway.vision_replies = [p01_reply()]
    owner = login_as("a@example.com")
    other = login_as("b@example.com")
    photo_id = upload(owner, new_draft(owner), JPEG).json()["photos"][0]["photo_id"]

    response = other.put(
        new_draft(other), json={"products": [{**supplement(), "photo_ids": [photo_id]}]}
    )

    assert response.status_code == 422
