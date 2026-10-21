"""照片物件儲存（Seam：PhotoStore，moto 模擬 S3）：只接受本模組產生的 object key。"""

import pytest

from nutrition_agent.photos import MEDICATION_PREFIX, PhotoNotFound, PhotoStore
from tests.conftest import bucket_keys

WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32


@pytest.mark.parametrize(
    "key",
    ["../photos/secret.jpg", "product/not-a-uuid.jpg", "avatar/" + "a" * 32 + ".jpg", ""],
)
def test_刪除格式不符的key會拋錯(photo_store: PhotoStore, key):
    with pytest.raises(ValueError):
        photo_store.delete(key)


def test_各種前綴與圖片格式存的key都能取網址與刪除(photo_store: PhotoStore, s3):
    key = photo_store.save(WEBP, ".webp", "image/webp", prefix=MEDICATION_PREFIX)

    assert photo_store.presigned_url(key)
    photo_store.delete(key)

    assert bucket_keys(s3) == []


def test_格式不符的key取不到網址(photo_store: PhotoStore):
    with pytest.raises(PhotoNotFound):
        photo_store.presigned_url("product/" + "a" * 32 + ".gif")
