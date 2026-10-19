"""FastAPI 進入點：create_app 可注入連線與模型閘道，測試用假實作。"""

from collections.abc import Callable, Iterator

import psycopg
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from nutrition_agent.api import assessments, auth, medication_photos, photos
from nutrition_agent.api.deps import (
    User,
    current_user,
    get_connection,
    get_gateway,
    get_photo_store,
)
from nutrition_agent.config import get_settings
from nutrition_agent.gateway import ModelGateway
from nutrition_agent.photos import PhotoStore

SESSION_MAX_AGE = 14 * 24 * 3600


class EchoRequest(BaseModel):
    prompt: str


def create_app(
    connection_provider: Callable[[], psycopg.Connection] | None = None,
    gateway: ModelGateway | None = None,
    photo_store: PhotoStore | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="nutrition-agent")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
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

    app.include_router(auth.router)
    app.include_router(assessments.router)
    app.include_router(photos.router)
    app.include_router(medication_photos.router)

    @app.post("/api/ping")
    def ping(conn: psycopg.Connection = Depends(get_connection)) -> dict:
        conn.execute("INSERT INTO ping DEFAULT VALUES")
        row = conn.execute("SELECT count(*) FROM ping").fetchone()
        return {"message": "pong", "count": row[0]}

    @app.post("/api/echo-llm")
    def echo_llm(
        body: EchoRequest,
        model: ModelGateway = Depends(get_gateway),
        _user: User = Depends(current_user),
    ) -> dict:
        return {"reply": model.complete(body.prompt)}

    return app


app = create_app()
