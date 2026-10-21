"""藥包照片：上傳 → VLM 只讀藥名原文 → 確定性查表對照。

照片辨識完存進物件儲存（medication/ 前綴），資料表記下每張讀出的藥名，方便回頭查 VLM
讀了什麼；照片本身不參與判定：使用者在清單上確認後，送出時後端仍以藥名原文重新對照。
"""

import psycopg
from fastapi import APIRouter, Depends, File, UploadFile

from nutrition_agent.api.assessments import _editable_draft, get_drug_names, get_reference
from nutrition_agent.api.deps import (
    User,
    current_user,
    get_connection,
    get_gateway,
    get_photo_store,
)
from nutrition_agent.api.photos import _discard
from nutrition_agent.api.uploads import (
    check_photo_count,
    model_service_errors,
    photo_storage_errors,
    read_upload,
)
from nutrition_agent.assessment.medications import resolve_medication
from nutrition_agent.extraction.medication_pack import UNREADABLE_HINT, read_medication_pack
from nutrition_agent.extraction.medication_pack import MedicationPackReading
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.photos import MEDICATION_PREFIX, PhotoStore
from nutrition_agent.reference import ReferenceData
from nutrition_agent.reference.drug_names import DrugNameTable, normalize_name

router = APIRouter(prefix="/api")

@router.post("/assessments/drafts/{draft_id}/medication-photos")
def recognize_medication_photos(
    draft_id: int,
    files: list[UploadFile] = File(default_factory=list),
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    gateway: ModelGateway = Depends(get_gateway),
    ref: ReferenceData = Depends(get_reference),
    table: DrugNameTable = Depends(get_drug_names),
    store: PhotoStore = Depends(get_photo_store),
) -> dict:
    """一批藥包照片 → 每張讀出的藥名，加上跨照片去重後的對照結果（範圍狀態）。"""
    _editable_draft(conn, draft_id, user)
    check_photo_count(len(files), "一次")
    uploads = [read_upload(f) for f in files]

    with model_service_errors("藥包 VLM"):
        readings = [read_medication_pack(gateway, data, mime) for data, mime, _ in uploads]
    # 先全部辨識完才存：模型服務出錯時 bucket 與資料表都不會多東西。
    _save_photos(conn, store, user, draft_id, uploads, readings)

    photos = [
        {"readable": r.readable, "names": r.names, "hint": None if r.readable else UNREADABLE_HINT}
        for r in readings
    ]
    unique: dict[str, str] = {}
    for reading in readings:
        for name in reading.names:
            unique.setdefault(normalize_name(name), name)
    medications = [
        resolve_medication(name, table, ref.drugs).model_dump(mode="json") for name in unique.values()
    ]
    return {"photos": photos, "medications": medications}


def _save_photos(
    conn: psycopg.Connection,
    store: PhotoStore,
    user: User,
    draft_id: int,
    uploads: list[tuple[bytes, str, str]],
    readings: list[MedicationPackReading],
) -> None:
    keys: list[str] = []
    try:
        with photo_storage_errors():
            for data, mime, ext in uploads:
                keys.append(store.save(data, ext, mime, prefix=MEDICATION_PREFIX))
        for key, (_, mime, _), reading in zip(keys, uploads, readings, strict=True):
            conn.execute(
                "INSERT INTO medication_photos (user_id, draft_id, stored_name, mime_type, names) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user.id, draft_id, key, mime, reading.names),
            )
    except Exception:
        _discard(store, keys)  # 中途失敗：本次已存的物件不留在 bucket
        raise
