"""照片上傳端點共用：張數上限、檔案檢查、存照片與失敗回收、模型服務與照片儲存的錯誤對應。"""

import logging
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import TypeVar

import httpx
from fastapi import HTTPException, UploadFile

from nutrition_agent.photo_normalization import (
    NORMALIZED_EXT,
    NORMALIZED_MIME,
    UnreadablePhoto,
    normalize_photo,
)
from nutrition_agent.photos import MAX_PHOTO_BYTES, PhotoStorageError, PhotoStore, sniff_image

MAX_PHOTOS_PER_PRODUCT = 8
MAX_PARALLEL_VLM = 4  # 同時辨識的照片數上限，避免撞到模型服務的限速

log = logging.getLogger(__name__)

Upload = tuple[bytes, str, str]  # (內容, MIME 類型, 副檔名)
R = TypeVar("R")
T = TypeVar("T")


def read_upload(upload: UploadFile) -> Upload:
    """回傳正規化後的 (內容, MIME 類型, 副檔名)；太大或不是支援的圖片格式就拒絕。

    大小與魔術位元組是第一道關卡，通過後才解碼正規化；辨識與存檔都用正規化後的版本。
    """
    data = upload.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="照片太大，請壓縮到 10 MB 以下再上傳")
    if sniff_image(data) is None:
        raise HTTPException(status_code=422, detail="只能上傳 JPEG、PNG 或 WebP 照片")
    try:
        normalized = normalize_photo(data)
    except UnreadablePhoto as err:
        log.warning("照片解不開：%s", err)
        raise HTTPException(
            status_code=422, detail="這張照片打不開，請重拍或換一張再上傳"
        ) from err
    return normalized, NORMALIZED_MIME, NORMALIZED_EXT


def check_photo_count(count: int, limit_prefix: str) -> None:
    """至少一張、最多 MAX_PHOTOS_PER_PRODUCT 張；limit_prefix 是超量訊息的開頭（如「一次」）。"""
    if count == 0:
        raise HTTPException(status_code=422, detail="請至少選一張照片")
    if count > MAX_PHOTOS_PER_PRODUCT:
        raise HTTPException(
            status_code=422, detail=f"{limit_prefix}最多 {MAX_PHOTOS_PER_PRODUCT} 張照片"
        )


def recognize_in_parallel(read: Callable[[bytes, str], R], uploads: Sequence[Upload]) -> list[R]:
    """每張照片各呼叫一次 read，最多 MAX_PARALLEL_VLM 張同時進行；結果依上傳順序排列。

    任一張丟出例外時，等其他張結束後原樣往外丟（呼叫端照舊包在 model_service_errors 裡），
    此時還沒存任何東西，所以失敗不會留下照片。read 不能碰資料庫連線（連線不跨執行緒）。
    """
    if not uploads:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_VLM, len(uploads))) as pool:
        return list(pool.map(lambda upload: read(upload[0], upload[1]), uploads))


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


@contextmanager
def stored_photos(
    store: PhotoStore,
    prefix: str,
    uploads: Sequence[Upload],
    readings: Sequence[R],
    write_row: Callable[[str, str, R], T],
) -> Iterator[list[T]]:
    """存入每張照片、以 write_row(key, mime, reading) 寫資料列，交出各列的回傳值。

    存檔、寫列，以及 with 區塊內之後的任何步驟出錯，本次已存的物件都會刪掉，不留孤兒物件；
    端點把交易結束前的所有步驟都放進 with 區塊。
    """
    keys: list[str] = []
    try:
        with photo_storage_errors():
            for data, mime, ext in uploads:
                keys.append(store.save(data, ext, mime, prefix=prefix))
        yield [
            write_row(key, mime, reading)
            for key, (_, mime, _), reading in zip(keys, uploads, readings, strict=True)
        ]
    except BaseException:
        _discard(store, keys)
        raise


def _discard(store: PhotoStore, keys: list[str]) -> None:
    for key in keys:
        try:
            store.delete(key)
        except PhotoStorageError:
            log.exception("清掉未寫入資料庫的照片物件失敗：%s", key)
