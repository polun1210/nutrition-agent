"""藥包照片：上傳 → VLM 只讀藥名原文 → 確定性查表對照。

照片不落地：只為了讀出藥名，使用者在清單上確認後，送出時後端仍以藥名原文重新對照。
"""

import psycopg
from fastapi import APIRouter, Depends, File, UploadFile

from nutrition_agent.api.assessments import _editable_draft, get_drug_names, get_reference
from nutrition_agent.api.deps import User, current_user, get_connection, get_gateway
from nutrition_agent.api.uploads import check_photo_count, model_service_errors, read_upload
from nutrition_agent.assessment.medications import resolve_medication
from nutrition_agent.extraction.medication_pack import UNREADABLE_HINT, read_medication_pack
from nutrition_agent.gateway import ModelGateway
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
) -> dict:
    """一批藥包照片 → 每張讀出的藥名，加上跨照片去重後的對照結果（範圍狀態）。"""
    _editable_draft(conn, draft_id, user)
    check_photo_count(len(files), "一次")
    uploads = [read_upload(f) for f in files]

    with model_service_errors("藥包 VLM"):
        readings = [read_medication_pack(gateway, data, mime) for data, mime, _ in uploads]

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
