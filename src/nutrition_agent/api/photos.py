"""保健食品照片：上傳辨識（預填校對頁）與取回照片。

照片與辨識結果都以 user.id 過濾；別人的草稿或照片一律 404，不洩漏是否存在。
"""

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from psycopg.types.json import Jsonb

from nutrition_agent.api.assessments import _editable_draft, get_reference
from nutrition_agent.api.deps import (
    User,
    current_user,
    get_connection,
    get_gateway,
    get_photo_store,
)
from nutrition_agent.api.uploads import check_photo_count, model_service_errors, read_upload
from nutrition_agent.extraction import VlmReading, build_extraction, read_label
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.photos import PhotoStore
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

    for (data, mime, ext), reading in zip(uploads, new_readings, strict=True):
        stored_name = store.save(data, ext)
        photo_id = conn.execute(
            "INSERT INTO product_photos (user_id, draft_id, stored_name, mime_type, reading) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user.id, draft_id, stored_name, mime, Jsonb(reading.model_dump(mode="json"))),
        ).fetchone()[0]
        readings.append((photo_id, reading))
    return build_extraction(readings, ref.ingredients).model_dump(mode="json")


@router.get("/photos/{photo_id}")
def get_photo(
    photo_id: int,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    store: PhotoStore = Depends(get_photo_store),
) -> Response:
    row = conn.execute(
        "SELECT stored_name, mime_type FROM product_photos WHERE id = %s AND user_id = %s",
        (photo_id, user.id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這張照片")
    try:
        data = store.read(row[0])
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail="找不到這張照片") from err
    return Response(content=data, media_type=row[1], headers={"Cache-Control": "private, max-age=3600"})
