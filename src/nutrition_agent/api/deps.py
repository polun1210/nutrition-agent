"""共用的 FastAPI 依賴：資料庫連線與登入者。

create_app 會在測試時用 dependency_overrides 換掉 get_connection / get_gateway。
受保護的路由一律 `user: User = Depends(current_user)`。
"""

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

import psycopg
from fastapi import Depends, HTTPException, Request

from nutrition_agent.config import get_settings
from nutrition_agent.gateway import ModelGateway, OpenRouterGateway
from nutrition_agent.photos import PhotoStore
from nutrition_agent.profile import Profile

SESSION_KEY = "user_id"
USER_COLUMNS = "id, email, birth_year, birth_month, sex, conditions"


def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_settings().database_url) as conn:
        yield conn  # 離開 with 時自動 commit


def get_gateway() -> ModelGateway:
    return OpenRouterGateway.from_settings(get_settings())


@lru_cache
def get_photo_store() -> PhotoStore:
    # boto3 client 建立成本高且執行緒安全，整個行程共用一個。
    return PhotoStore.from_settings(get_settings())


@dataclass(frozen=True)
class User:
    id: int
    email: str
    profile: Profile


def current_user(request: Request, conn: psycopg.Connection = Depends(get_connection)) -> User:
    user_id = request.session.get(SESSION_KEY)
    row = (
        conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (user_id,)).fetchone()
        if user_id is not None
        else None
    )
    if row is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="請先登入")
    return User(
        id=row[0],
        email=row[1],
        profile=Profile(birth_year=row[2], birth_month=row[3], sex=row[4], conditions=row[5]),
    )
