"""帳號 API：註冊、登入、登出、個人資料。

登入狀態放在簽章的 cookie session（Starlette SessionMiddleware），
密碼雜湊用 pwdlib（Argon2）。
"""

from datetime import date
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field

from nutrition_agent.accounts import UnderageError, age_on, require_adult
from nutrition_agent.api.deps import SESSION_KEY, User, current_user, get_connection
from nutrition_agent.profile import Profile

_hasher = PasswordHash.recommended()
# 查無帳號時也跑一次雜湊比對，避免從回應時間推測 email 是否存在。
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

router = APIRouter(prefix="/api")


class RegisterRequest(Profile):
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/register", status_code=201)
def register(
    body: RegisterRequest, request: Request, conn: psycopg.Connection = Depends(get_connection)
) -> dict:
    row = conn.execute(
        "INSERT INTO users (email, password_hash, birth_year, birth_month, sex, conditions) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (lower(email)) DO NOTHING RETURNING id",
        (
            body.email,
            _hasher.hash(body.password),
            body.birth_year,
            body.birth_month,
            body.sex,
            body.conditions,
        ),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=409, detail="這個 email 已經註冊過")
    request.session[SESSION_KEY] = row[0]
    return {"id": row[0]}


@router.post("/auth/login")
def login(
    body: LoginRequest, request: Request, conn: psycopg.Connection = Depends(get_connection)
) -> dict:
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE lower(email) = lower(%s)", (body.email,)
    ).fetchone()
    valid = _hasher.verify(body.password, row[1] if row else _DUMMY_HASH)
    if row is None or not valid:
        raise HTTPException(status_code=401, detail="email 或密碼錯誤")
    request.session.clear()
    request.session[SESSION_KEY] = row[0]
    return {"id": row[0]}


@router.post("/auth/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    today = date.today()
    profile = user.profile
    underage_message = None
    try:
        require_adult(profile.birth_year, profile.birth_month, today)
    except UnderageError as err:
        underage_message = str(err)
    return {
        "id": user.id,
        "email": user.email,
        "profile": profile.model_dump(),
        "age": age_on(profile.birth_year, profile.birth_month, today),
        "is_adult": underage_message is None,
        "underage_message": underage_message,
    }


@router.put("/me/profile")
def update_profile(
    body: Profile,
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_connection),
) -> dict:
    conn.execute(
        "UPDATE users SET birth_year = %s, birth_month = %s, sex = %s, conditions = %s "
        "WHERE id = %s",
        (body.birth_year, body.birth_month, body.sex, body.conditions, user.id),
    )
    return {"profile": body.model_dump()}
