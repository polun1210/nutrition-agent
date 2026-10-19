"""藥包照片（Seam：HTTP API，假模型閘道）：VLM 只讀字，藥名對照沿用確定性查表；送出時後端照樣重新對照。"""

import json

import httpx

from tests.test_medications_api import profile_text, save

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def pack(*names, readable=True):
    return json.dumps({"readable": readable, "names": list(names)}, ensure_ascii=False)


def new_draft(client):
    return client.post("/api/assessments/drafts").json()["id"]


def upload(client, draft_id, *images):
    files = [("files", (f"m{i}.jpg", image, "image/jpeg")) for i, image in enumerate(images)]
    return client.post(f"/api/assessments/drafts/{draft_id}/medication-photos", files=files)


def test_一批多張照片每張多個藥名並顯示範圍狀態(login_as, gateway):
    gateway.vision_replies = [pack("Amlodipine", "Zantac"), pack("Bisoprolol", "完全沒聽過的藥")]
    client = login_as()

    response = upload(client, new_draft(client), JPEG, PNG)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [p["readable"] for p in body["photos"]] == [True, True]
    assert [p["names"] for p in body["photos"]] == [["Amlodipine", "Zantac"], ["Bisoprolol", "完全沒聽過的藥"]]
    status = {m["raw_name"]: m["scope_status"] for m in body["medications"]}
    assert status == {
        "Amlodipine": "in_scope",
        "Zantac": "out_of_scope",
        "Bisoprolol": "out_of_scope",
        "完全沒聽過的藥": "unconfirmed",
    }
    assert len(gateway.calls) == 2


def test_跨照片重複的藥名只留一個(login_as, gateway):
    gateway.vision_replies = [pack("Amlodipine"), pack("amlodipine", "Zantac")]
    client = login_as()

    body = upload(client, new_draft(client), JPEG, PNG).json()

    assert [m["raw_name"] for m in body["medications"]] == ["Amlodipine", "Zantac"]


def test_讀不到的照片指出是哪一張並附重拍提示(login_as, gateway):
    gateway.vision_replies = [pack("Amlodipine"), "抱歉我看不懂"]
    client = login_as()

    body = upload(client, new_draft(client), JPEG, PNG).json()

    first, second = body["photos"]
    assert first["readable"] is True and first["hint"] is None
    assert second["readable"] is False and "重拍" in second["hint"] and second["names"] == []
    assert [m["raw_name"] for m in body["medications"]] == ["Amlodipine"]


def test_模型服務故障回502(login_as, gateway):
    gateway.vision_replies = [httpx.ConnectError("down")]
    client = login_as()

    response = upload(client, new_draft(client), JPEG)

    assert response.status_code == 502


def test_檔案格式與數量檢查(login_as, gateway):
    client = login_as()
    draft_id = new_draft(client)

    assert upload(client, draft_id).status_code == 422
    assert upload(client, draft_id, b"not an image").status_code == 422
    assert upload(client, draft_id, *[JPEG] * 9).status_code == 422
    assert gateway.calls == []


def test_別人的草稿與未登入都不能用(login_as, make_client, gateway):
    owner = login_as("a@example.com")
    draft_id = new_draft(owner)
    other = login_as("b@example.com")

    assert upload(other, draft_id, JPEG).status_code == 404
    assert upload(make_client(), draft_id, JPEG).status_code == 401
    assert gateway.calls == []


def test_讀出的藥名經草稿送出後後端重新對照(login_as, gateway):
    gateway.vision_replies = [pack("Amlodipine")]
    client = login_as()
    draft_id = new_draft(client)
    names = [m["raw_name"] for m in upload(client, draft_id, JPEG).json()["medications"]]

    assert save(client, draft_id, [{"name": n, "scope_status": "in_scope"} for n in names]).status_code == 200
    case_id = client.post(f"/api/assessments/drafts/{draft_id}/submit").json()["id"]

    assert "Amlodipine" in profile_text(client, case_id)
