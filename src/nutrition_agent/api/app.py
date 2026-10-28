"""FastAPI 進入點：create_app 可注入連線與模型閘道，測試用假實作。"""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

from nutrition_agent.api import assessments, auth, health, medication_photos, photos
from nutrition_agent.api.deps import (
    get_connection,
    get_gateway,
    get_photo_store,
)
from nutrition_agent.config import get_settings, resolve_session_secret
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.photos import PhotoStore

SESSION_MAX_AGE = 14 * 24 * 3600


def create_app(
    connection_provider: Callable[[], psycopg.Connection] | None = None,
    gateway: ModelGateway | None = None,
    photo_store: PhotoStore | None = None,
) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # 啟動時才連物件儲存（import 模組不連線）；bucket 不存在就建立。
        (photo_store or get_photo_store()).ensure_bucket()
        yield

    app = FastAPI(title="nutrition-agent", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=resolve_session_secret(settings),
        max_age=SESSION_MAX_AGE,
        same_site="lax",
        https_only=settings.session_https_only,
    )

    if connection_provider is not None:
        # 測試注入的連線由測試夾具管理交易，這裡不 commit。
        def injected_connection() -> Iterator[psycopg.Connection]:
            yield connection_provider()

        app.dependency_overrides[get_connection] = injected_connection
    if gateway is not None:
        app.dependency_overrides[get_gateway] = lambda: gateway
    if photo_store is not None:
        app.dependency_overrides[get_photo_store] = lambda: photo_store

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(assessments.router)
    app.include_router(photos.router)
    app.include_router(medication_photos.router)

    @app.post("/api/ping")
    def ping(conn: psycopg.Connection = Depends(get_connection)) -> dict:
        conn.execute("INSERT INTO ping DEFAULT VALUES")
        row = conn.execute("SELECT count(*) FROM ping").fetchone()
        return {"message": "pong", "count": row[0]}

    return app


app = create_app()
