"""照片上傳端點共用：張數上限、檔案檢查、模型服務與照片儲存的錯誤對應。"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from fastapi import HTTPException, UploadFile

from nutrition_agent.photos import MAX_PHOTO_BYTES, PhotoStorageError, sniff_image

MAX_PHOTOS_PER_PRODUCT = 8

log = logging.getLogger(__name__)


def read_upload(upload: UploadFile) -> tuple[bytes, str, str]:
    """回傳 (內容, MIME 類型, 副檔名)；太大或不是支援的圖片格式就拒絕。"""
    data = upload.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="照片太大，請壓縮到 10 MB 以下再上傳")
    kind = sniff_image(data)
    if kind is None:
        raise HTTPException(status_code=422, detail="只能上傳 JPEG、PNG 或 WebP 照片")
    return data, kind[0], kind[1]


def check_photo_count(count: int, limit_prefix: str) -> None:
    """至少一張、最多 MAX_PHOTOS_PER_PRODUCT 張；limit_prefix 是超量訊息的開頭（如「一次」）。"""
    if count == 0:
        raise HTTPException(status_code=422, detail="請至少選一張照片")
    if count > MAX_PHOTOS_PER_PRODUCT:
        raise HTTPException(
            status_code=422, detail=f"{limit_prefix}最多 {MAX_PHOTOS_PER_PRODUCT} 張照片"
        )


@contextmanager
def model_service_errors(what: str) -> Iterator[None]:
    """模型服務連線／回應錯誤一律對外回 502，細節只進 log。"""
    try:
        yield
    except httpx.HTTPError as err:
        log.exception("%s 呼叫失敗", what)
        raise HTTPException(status_code=502, detail="辨識服務暫時無法使用，請稍後再試") from err


@contextmanager
def photo_storage_errors() -> Iterator[None]:
    """照片物件儲存故障一律對外回 502，細節只進 log。"""
    try:
        yield
    except PhotoStorageError as err:
        log.exception("照片物件儲存操作失敗")
        raise HTTPException(
            status_code=502, detail="照片儲存服務暫時無法使用，請稍後再試"
        ) from err
