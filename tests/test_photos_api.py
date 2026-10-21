"""保健食品照片：上傳 → 辨識（假模型閘道）→ 預填；照片只有本人拿得到。"""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient

from nutrition_agent.api.app import create_app
from nutrition_agent.photos import PhotoStore
from tests.conftest import TEST_BUCKET, TEST_PHOTO_URL_TTL, TEST_PUBLIC_S3_ENDPOINT, bucket_keys
from tests.test_assessments_api import supplement

STORAGE_DOWN = "照片儲存服務暫時無法使用，請稍後再試"

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


def test_上傳後照片存進bucket且key不含使用者資訊(login_as, gateway, s3):
    gateway.vision_replies = [p01_reply()]
    client = login_as("someone@example.com")

    assert upload(client, new_draft(client), JPEG).status_code == 200

    [key] = bucket_keys(s3)
    assert re.fullmatch(r"product/[0-9a-f]{32}\.jpg", key)
    stored = s3.get_object(Bucket=TEST_BUCKET, Key=key)
    assert stored["Body"].read() == JPEG and stored["ContentType"] == "image/jpeg"


def test_照片只有本人拿得到(login_as, make_client, gateway):
    gateway.vision_replies = [p01_reply()]
    owner = login_as("a@example.com")
    other = login_as("b@example.com")
    photo_id = upload(owner, new_draft(owner), JPEG).json()["photos"][0]["photo_id"]

    assert owner.get(f"/api/photos/{photo_id}", follow_redirects=False).status_code == 302
    assert other.get(f"/api/photos/{photo_id}", follow_redirects=False).status_code == 404
    assert make_client().get(f"/api/photos/{photo_id}").status_code == 401
    assert owner.get("/api/photos/999999", follow_redirects=False).status_code == 404


def test_取照片導向公開endpoint簽的短效網址(login_as, gateway, s3):
    gateway.vision_replies = [p01_reply()]
    client = login_as()
    photo_id = upload(client, new_draft(client), JPEG).json()["photos"][0]["photo_id"]
    [key] = bucket_keys(s3)

    response = client.get(f"/api/photos/{photo_id}", follow_redirects=False)

    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    # 簽章綁 host：一定要用瀏覽器連得到的公開 endpoint 簽，不能簽內部的再改 host。
    assert f"{location.scheme}://{location.netloc}" == TEST_PUBLIC_S3_ENDPOINT
    assert location.path == f"/{TEST_BUCKET}/{key}"
    query = parse_qs(location.query)
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == [str(TEST_PHOTO_URL_TTL)]
    assert query["X-Amz-Signature"][0]
    # 導向本身不能被快取：網址失效後瀏覽器要重新問 API。
    assert "no-store" in response.headers["cache-control"]


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


def test_模型服務故障時回報稍後再試且不留下照片(login_as, gateway, db, s3):
    gateway.vision_replies = [httpx.ConnectError("boom")]
    client = login_as()

    response = upload(client, new_draft(client), JPEG)

    assert response.status_code == 502
    assert db.execute("SELECT count(*) FROM product_photos").fetchone()[0] == 0
    assert bucket_keys(s3) == []


def fail_storage(s3, operation: str, after: int = 0) -> None:
    """讓物件儲存的某個操作在成功 after 次之後連不上（走真實的 botocore 例外路徑）。"""
    calls = []

    def boom(request, **_):
        calls.append(request)
        if len(calls) > after:
            raise EndpointConnectionError(endpoint_url=request.url)

    s3.meta.events.register(f"before-send.s3.{operation}", boom)


def test_儲存服務故障時上傳回報稍後再試且不留下照片(login_as, gateway, db, s3):
    gateway.vision_replies = [p01_reply(), BACK]
    client = login_as()
    fail_storage(s3, "PutObject", after=1)  # 第一張存進去、第二張失敗

    response = upload(client, new_draft(client), JPEG, PNG)

    assert response.status_code == 502
    assert response.json()["detail"] == STORAGE_DOWN
    assert bucket_keys(s3) == []
    assert db.execute("SELECT count(*) FROM product_photos").fetchone()[0] == 0


def test_存檔之後的步驟失敗也不留下照片(login_as, gateway, s3, monkeypatch):
    gateway.vision_replies = [p01_reply()]
    client = login_as()

    def broken(*_):
        raise RuntimeError("合併失敗")

    monkeypatch.setattr("nutrition_agent.api.photos.build_extraction", broken)

    with pytest.raises(RuntimeError):
        upload(client, new_draft(client), JPEG)

    assert bucket_keys(s3) == []


def test_API啟動時自動建立不存在的bucket(s3):
    store = PhotoStore(s3, "fresh-bucket", s3, TEST_PHOTO_URL_TTL)

    with TestClient(create_app(photo_store=store)):
        pass

    assert s3.head_bucket(Bucket="fresh-bucket")["ResponseMetadata"]["HTTPStatusCode"] == 200


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


def expire_photo(db, photo_id: int) -> None:
    """模擬保存期限已過（清理工作之後由 #29 提供）。"""
    db.execute("UPDATE product_photos SET expired_at = now() WHERE id = %s", (photo_id,))


def test_過期的照片本人拿到410別人仍是404(login_as, gateway, db):
    gateway.vision_replies = [p01_reply()]
    owner = login_as("a@example.com")
    other = login_as("b@example.com")
    photo_id = upload(owner, new_draft(owner), JPEG).json()["photos"][0]["photo_id"]

    expire_photo(db, photo_id)

    assert owner.get(f"/api/photos/{photo_id}", follow_redirects=False).status_code == 410
    assert other.get(f"/api/photos/{photo_id}", follow_redirects=False).status_code == 404

