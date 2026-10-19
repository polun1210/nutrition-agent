"""FastAPI 進入點：create_app 可注入連線與模型閘道，測試用假實作。"""

from collections.abc import Callable, Iterator

import psycopg
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from nutrition_agent.config import get_settings
from nutrition_agent.gateway import ModelGateway, OpenRouterGateway


class EchoRequest(BaseModel):
    prompt: str


def create_app(
    connection_provider: Callable[[], psycopg.Connection] | None = None,
    gateway: ModelGateway | None = None,
) -> FastAPI:
    app = FastAPI(title="nutrition-agent")

    def get_connection() -> Iterator[psycopg.Connection]:
        if connection_provider is not None:
            # 測試注入的連線由測試夾具管理交易，這裡不 commit。
            yield connection_provider()
            return
        with psycopg.connect(get_settings().database_url) as conn:
            yield conn  # 離開 with 時自動 commit

    def get_gateway() -> ModelGateway:
        return gateway or OpenRouterGateway.from_settings(get_settings())

    @app.post("/api/ping")
    def ping(conn: psycopg.Connection = Depends(get_connection)) -> dict:
        conn.execute("INSERT INTO ping DEFAULT VALUES")
        row = conn.execute("SELECT count(*) FROM ping").fetchone()
        return {"message": "pong", "count": row[0]}

    @app.post("/api/echo-llm")
    def echo_llm(body: EchoRequest, model: ModelGateway = Depends(get_gateway)) -> dict:
        return {"reply": model.complete(body.prompt)}

    return app


app = create_app()
