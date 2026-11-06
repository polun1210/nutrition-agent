"""照片正規化（Seam：HTTP API，假模型閘道＋moto）：保健食品與藥包兩條路徑行為一致。

存進物件儲存的、送給 VLM 的，都是同一張轉正、縮小、無中繼資料的 JPEG。
"""

import pytest

from tests.conftest import TEST_BUCKET, bucket_keys
from tests.images import MAGIC_ONLY_JPEG, PNG, decompression_bomb_png, make_image, open_image

PATHS = {
    "product": "photos",
    "medication": "medication-photos",
}


@pytest.fixture(params=sorted(PATHS))
def upload(request, login_as):
    """上傳到其中一條照片路徑；兩條路徑跑同一組測試。"""
    client = login_as()
    draft_id = client.post("/api/assessments/drafts").json()["id"]
    url = f"/api/assessments/drafts/{draft_id}/{PATHS[request.param]}"

    def _upload(*images: bytes):
        files = [("files", (f"p{i}.jpg", image, "image/jpeg")) for i, image in enumerate(images)]
        return client.post(url, files=files)

    return _upload


def stored_objects(s3) -> list[dict]:
    return [s3.get_object(Bucket=TEST_BUCKET, Key=key) for key in bucket_keys(s3)]


def test_存下的與送給VLM的是同一張JPEG(upload, gateway, s3):
    assert upload(PNG).status_code == 200

    [stored] = stored_objects(s3)
    data = stored["Body"].read()
    assert stored["ContentType"] == "image/jpeg"
    assert open_image(data).format == "JPEG"
    assert gateway.images == [(data, "image/jpeg")]


def test_依EXIF方向轉正(upload, s3):
    # EXIF 方向 6：存的是橫圖，要順時針轉 90 度才是正的，存檔的左上角會轉到右上角。
    sideways = make_image("JPEG", (80, 40), marker="red", orientation=6)

    assert upload(sideways).status_code == 200

    [stored] = stored_objects(s3)
    image = open_image(stored["Body"].read())
    assert image.size == (40, 80)
    assert is_red(image.getpixel((37, 2)))
    assert not is_red(image.getpixel((2, 2)))


@pytest.mark.parametrize(
    ("original", "normalized"),
    [
        ((3200, 1000), (1600, 500)),  # 長邊縮到 1600，等比例
        ((1200, 2400), (800, 1600)),  # 直的也是看長邊
        ((800, 600), (800, 600)),  # 不放大
    ],
)
def test_長邊超過1600像素時等比例縮小(upload, s3, original, normalized):
    assert upload(make_image("PNG", original)).status_code == 200

    [stored] = stored_objects(s3)
    assert open_image(stored["Body"].read()).size == normalized


@pytest.mark.parametrize(
    ("fmt", "mode", "transparent"),
    [("PNG", "RGBA", (0, 0, 0, 0)), ("WEBP", "RGBA", (0, 0, 0, 0)), ("PNG", "LA", (0, 0))],
)
def test_透明部分補成白色(upload, s3, fmt, mode, transparent):
    photo = make_image(fmt, mode=mode, color=transparent)

    assert upload(photo).status_code == 200

    [stored] = stored_objects(s3)
    image = open_image(stored["Body"].read())
    assert image.mode == "RGB"
    assert all(channel > 245 for channel in image.getpixel((10, 10)))


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_不保留拍攝地點等任何中繼資料(upload, s3, fmt):
    photo = make_image(fmt, orientation=1, gps=True)

    assert upload(photo).status_code == 200

    [stored] = stored_objects(s3)
    image = open_image(stored["Body"].read())
    assert len(image.getexif()) == 0
    assert not {"exif", "icc_profile", "xmp", "comment"} & set(image.info)


def is_red(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red > 200 and green < 60 and blue < 60  # JPEG 有損，不比對確切值


def test_解不開的照片回422請使用者重拍且不存任何東西(upload, gateway, s3):
    response = upload(PNG, MAGIC_ONLY_JPEG)

    assert response.status_code == 422
    assert "重拍" in response.json()["detail"]
    assert bucket_keys(s3) == []
    assert gateway.images == []


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_解壓縮炸彈回422且不存任何東西(upload, gateway, s3):
    response = upload(decompression_bomb_png())

    assert response.status_code == 422
    assert "重拍" in response.json()["detail"]
    assert bucket_keys(s3) == []
    assert gateway.images == []
