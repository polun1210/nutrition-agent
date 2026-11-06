"""一次多張照片時 VLM 平行辨識（Seam：HTTP API，假模型閘道依圖片尺寸回覆）。"""

import json
import threading
import time

import httpx
import pytest

from nutrition_agent.api.uploads import MAX_PARALLEL_VLM
from tests.conftest import bucket_keys
from tests.images import JPEG, TALL, WIDE, make_image, size_of
from tests.test_medication_photos_api import pack
from tests.test_photos_api import BACK, UNREADABLE, p01_reply

PRODUCT = "photos"
MEDICATION = "medication-photos"


def post(client, endpoint, *images):
    draft_id = client.post("/api/assessments/drafts").json()["id"]
    files = [("files", (f"x{i}.jpg", image, "image/jpeg")) for i, image in enumerate(images)]
    return client.post(f"/api/assessments/drafts/{draft_id}/{endpoint}", files=files)


def distinct_images(count):
    return [make_image("JPEG", (40 + i, 30)) for i in range(count)]


def test_保健食品照片的辨識結果依上傳順序對應(login_as, gateway):
    gateway.vision_by_size = {size_of(JPEG): UNREADABLE, size_of(WIDE): p01_reply(), size_of(TALL): BACK}
    client = login_as()

    body = post(client, PRODUCT, JPEG, WIDE, TALL).json()

    assert [p["readable"] for p in body["photos"]] == [False, True, True]
    assert body["product_name"] == "挺立 葡萄糖胺強力錠"


def test_藥包照片的辨識結果依上傳順序對應(login_as, gateway, db):
    gateway.vision_by_size = {
        size_of(JPEG): pack("Zantac"),
        size_of(WIDE): pack("Amlodipine"),
        size_of(TALL): pack("Bisoprolol"),
    }
    client = login_as()

    body = post(client, MEDICATION, JPEG, WIDE, TALL).json()

    assert [p["names"] for p in body["photos"]] == [["Zantac"], ["Amlodipine"], ["Bisoprolol"]]
    rows = db.execute("SELECT names FROM medication_photos ORDER BY id").fetchall()
    assert [r[0] for r in rows] == [["Zantac"], ["Amlodipine"], ["Bisoprolol"]]


@pytest.mark.parametrize(("endpoint", "reply"), [(PRODUCT, BACK), (MEDICATION, pack("Amlodipine"))])
def test_多張照片同時辨識且並行數有上限(login_as, gateway, endpoint, reply):
    # 循序執行時第一張會卡在 barrier 等不到同伴而逾時；並行超過上限時 peak 會變大。
    barrier = threading.Barrier(MAX_PARALLEL_VLM, timeout=5)
    lock = threading.Lock()
    active = peak = 0
    original = gateway.vision

    def vision(prompt, image, mime_type, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait()
        time.sleep(0.05)
        with lock:
            active -= 1
        return original(prompt, image, mime_type, **kwargs)

    gateway.vision_reply = reply
    gateway.vision = vision
    client = login_as()

    response = post(client, endpoint, *distinct_images(2 * MAX_PARALLEL_VLM))

    assert response.status_code == 200, response.text
    assert peak == MAX_PARALLEL_VLM
    assert len(gateway.images) == 2 * MAX_PARALLEL_VLM


@pytest.mark.parametrize(
    ("endpoint", "table", "ok"),
    [(PRODUCT, "product_photos", BACK), (MEDICATION, "medication_photos", pack("Amlodipine"))],
)
def test_平行辨識中任一張故障整批回502且不留下東西(login_as, gateway, db, s3, endpoint, table, ok):
    gateway.vision_by_size = {
        size_of(JPEG): ok,
        size_of(WIDE): httpx.ConnectError("down"),
        size_of(TALL): ok,
    }
    client = login_as()

    response = post(client, endpoint, JPEG, WIDE, TALL)

    assert response.status_code == 502
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert bucket_keys(s3) == []


def test_假閘道依圖片尺寸回覆():
    from tests.fakes import FakeGateway

    gateway = FakeGateway(vision_by_size={size_of(WIDE): json.dumps({"a": 1})})

    assert gateway.vision("p", WIDE, "image/jpeg") == '{"a": 1}'
