"""評估 API：草稿逐步儲存 → 送出成不可變的評估個案 → 報告。

所有查詢都以 `user.id` 過濾；別人的草稿與個案一律回 404。
送出時後端自己組快照（個人資料取當下最新值、年齡以今天計）並跑判定引擎與報告模板，
結果整份凍結進 assessment_cases。
"""

from datetime import date
from functools import lru_cache

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from nutrition_agent.accounts import UnderageError, require_adult
from nutrition_agent.api.deps import User, current_user, get_connection
from nutrition_agent.assessment import (
    UNKNOWN_INGREDIENT,
    AssessmentCase,
    Product,
    ProfileSnapshot,
    assess,
)
from nutrition_agent.reference import ReferenceData, load_reference_data
from nutrition_agent.reporting.template import render_report

router = APIRouter(prefix="/api/assessments")


@lru_cache
def get_reference() -> ReferenceData:
    return load_reference_data()


class DraftBody(BaseModel):
    products: list[Product]


def _draft_row(conn: psycopg.Connection, draft_id: int, user: User) -> tuple:
    row = conn.execute(
        "SELECT id, products, case_id FROM assessment_drafts WHERE id = %s AND user_id = %s",
        (draft_id, user.id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這份評估草稿")
    return row


def _editable_draft(conn: psycopg.Connection, draft_id: int, user: User) -> tuple:
    row = _draft_row(conn, draft_id, user)
    if row[2] is not None:
        raise HTTPException(status_code=409, detail="這份評估已送出，不能再修改")
    return row


def _check_ingredient_codes(products: list[Product], ref: ReferenceData) -> None:
    known = ref.ingredients.codes() | {UNKNOWN_INGREDIENT}
    for product in products:
        for item in product.ingredients:
            if item.ingredient_code not in known:
                raise HTTPException(
                    status_code=422, detail=f"成分只能從選單挑選：{item.ingredient_code}"
                )


def _draft_json(row: tuple) -> dict:
    return {"id": row[0], "products": row[1], "submitted_case_id": row[2]}


@router.post("/drafts", status_code=201)
def create_draft(
    user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_connection)
) -> dict:
    row = conn.execute(
        "INSERT INTO assessment_drafts (user_id) VALUES (%s) RETURNING id, products, case_id",
        (user.id,),
    ).fetchone()
    return _draft_json(row)


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: int,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
) -> dict:
    return _draft_json(_draft_row(conn, draft_id, user))


@router.put("/drafts/{draft_id}")
def save_draft(
    draft_id: int,
    body: DraftBody,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    ref: ReferenceData = Depends(get_reference),
) -> dict:
    _editable_draft(conn, draft_id, user)
    _check_ingredient_codes(body.products, ref)
    row = conn.execute(
        "UPDATE assessment_drafts SET products = %s, updated_at = now() WHERE id = %s "
        "RETURNING id, products, case_id",
        (Jsonb([p.model_dump(mode="json") for p in body.products]), draft_id),
    ).fetchone()
    return _draft_json(row)


@router.post("/drafts/{draft_id}/submit", status_code=201)
def submit_draft(
    draft_id: int,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
    ref: ReferenceData = Depends(get_reference),
) -> dict:
    row = _editable_draft(conn, draft_id, user)
    products = [Product.model_validate(p) for p in row[1]]
    if not products:
        raise HTTPException(status_code=422, detail="至少要有一項保健食品才能送出")
    today = date.today()
    profile = user.profile
    try:
        age = require_adult(profile.birth_year, profile.birth_month, today)
    except UnderageError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err

    case = AssessmentCase(
        profile=ProfileSnapshot(**profile.model_dump()),
        age=age,
        assessed_on=today,
        products=products,
    )
    assessment = assess(case, ref)
    report = render_report(case, assessment, ref)
    case_id = conn.execute(
        "INSERT INTO assessment_cases (user_id, snapshot, assessment, report, reference_versions) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (
            user.id,
            Jsonb(case.model_dump(mode="json")),
            Jsonb(assessment.model_dump(mode="json")),
            Jsonb(report.model_dump(mode="json")),
            Jsonb(ref.versions),
        ),
    ).fetchone()[0]
    conn.execute("UPDATE assessment_drafts SET case_id = %s WHERE id = %s", (case_id, draft_id))
    return {"id": case_id}


@router.get("/{case_id}")
def get_case(
    case_id: int,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
) -> dict:
    row = conn.execute(
        "SELECT id, snapshot, assessment, report, reference_versions, created_at "
        "FROM assessment_cases WHERE id = %s AND user_id = %s",
        (case_id, user.id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這份評估")
    snapshot = row[1]
    return {
        "id": row[0],
        **snapshot,  # profile、age、assessed_on、products
        "assessment": row[2],
        "report": row[3],
        "reference_versions": row[4],
        "created_at": row[5].isoformat(),
    }
