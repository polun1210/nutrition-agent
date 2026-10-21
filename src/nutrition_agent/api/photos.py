"""保健食品照片：上傳辨識（預填校對頁）與取回照片。

照片與辨識結果都以 user.id 過濾；別人的草稿或照片一律 404，不洩漏是否存在。
"""

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from psycopg.types.json import Jsonb

from nutrition_agent.api.assessments import _editable_draft, get_reference
from nutrition_agent.api.deps import (
    User,
    current_user,
    get_connection,
    get_gateway,
    get_photo_store,
)
from nutrition_agent.api.uploads import (
    check_photo_count,
    model_service_errors,
    photo_storage_errors,
    read_upload,
    stored_photos,
)
from nutrition_agent.extraction import VlmReading, build_extraction, read_label
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.photos import PRODUCT_PREFIX, PhotoNotFound, PhotoStore
from nutrition_agent.reference import ReferenceData

router = APIRouter(prefix="/api")


def _existing_readings(
    conn: psycopg.Connection, user: User, draft_id: int, photo_ids: list[int]
) -> list[tuple[int, VlmReading]]:
    rows = conn.execute(
        "SELECT id, reading FROM product_photos "
        "WHERE id = ANY(%s) AND user_id = %s AND draft_id = %s",
        (photo_ids, user.id, draft_id),
    ).fetchall()
    by_id = {row[0]: VlmReading.model_validate(row[1]) for row in rows}
    if set(by_id) != set(photo_ids):
        raise HTTPException(status_code=404, detail="找不到這張照片")
    return [(photo_id, by_id[photo_id]) for photo_id in photo_ids]


@router.post("/assessments/drafts/{draft_id}/photos")
def recognize_photos(
    draft_id: int,
    files: list[UploadFile] = File(default_factory=list),
    photo_ids: list[int] = Form(default_factory=list),
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    gateway: ModelGateway = Depends(get_gateway),
    store: PhotoStore = Depends(get_photo_store),
    ref: ReferenceData = Depends(get_reference),
) -> dict:
    """同一項產品的多張照片（新上傳的檔案＋先前已辨識的照片編號）合併成一筆預填結果。"""
    _editable_draft(conn, draft_id, user)
    check_photo_count(len(files) + len(photo_ids), "同一項產品")
    uploads = [read_upload(f) for f in files]
    readings = _existing_readings(conn, user, draft_id, photo_ids)

    # 先全部辨識完才存檔：模型服務出錯時不會留下沒用的照片。
    with model_service_errors("VLM"):
        new_readings = [read_label(gateway, data, mime) for data, mime, _ in uploads]

    def write_row(key: str, mime: str, reading: VlmReading) -> int:
        return conn.execute(
            "INSERT INTO product_photos (user_id, draft_id, stored_name, mime_type, reading) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user.id, draft_id, key, mime, Jsonb(reading.model_dump(mode="json"))),
        ).fetchone()[0]

    with stored_photos(store, PRODUCT_PREFIX, uploads, new_readings, write_row) as photo_ids:
        merged = [*readings, *zip(photo_ids, new_readings, strict=True)]
        return build_extraction(merged, ref.ingredients).model_dump(mode="json")


@router.get("/photos/{photo_id}")
def get_photo(
    photo_id: int,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    store: PhotoStore = Depends(get_photo_store),
) -> RedirectResponse:
    """確認是本人的照片後，302 導向短效 presigned URL，讓瀏覽器直接向物件儲存取圖。"""
    row = conn.execute(
        "SELECT stored_name, expired_at FROM product_photos WHERE id = %s AND user_id = %s",
        (photo_id, user.id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這張照片")
    if row[1] is not None:  # 先確認是本人的照片才回 410，別人的照片不洩漏存在與否
        raise HTTPException(status_code=410, detail="照片已超過保存期限")
    try:
        with photo_storage_errors():
            url = store.presigned_url(row[0])
    except PhotoNotFound as err:
        raise HTTPException(status_code=404, detail="找不到這張照片") from err
    # 導向不能被快取，否則網址過期後瀏覽器還會沿用舊的導向。
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
