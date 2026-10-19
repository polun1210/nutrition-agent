"""測試夾具：本機測試資料庫、每個測試獨立的交易、假模型閘道。"""

import os
from collections.abc import Callable, Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import conninfo, sql

from nutrition_agent.api.app import create_app
from nutrition_agent.config import to_sqlalchemy_url
from tests.fakes import FakeGateway

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition_test",
)


def _recreate_database(url: str) -> None:
    name = conninfo.conninfo_to_dict(url)["dbname"]
    admin = conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def database_url() -> str:
    _recreate_database(TEST_DATABASE_URL)
    config = Config("alembic.ini")
    config.attributes["url"] = to_sqlalchemy_url(TEST_DATABASE_URL)
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
def db(database_url: str) -> Iterator[psycopg.Connection]:
    """每個測試一條連線、一個交易，結束時 rollback，測試之間互不影響。"""
    with psycopg.connect(database_url) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def app(db: psycopg.Connection, gateway: FakeGateway) -> FastAPI:
    return create_app(connection_provider=lambda: db, gateway=gateway)


@pytest.fixture
def make_client(app: FastAPI) -> Iterator[Callable[[], TestClient]]:
    """每次呼叫回傳一個有獨立 cookie 的客戶端（模擬不同使用者的瀏覽器）。"""
    clients: list[TestClient] = []

    def _make() -> TestClient:
        test_client = TestClient(app)
        clients.append(test_client)
        return test_client

    yield _make
    for test_client in clients:
        test_client.close()


@pytest.fixture
def client(make_client: Callable[[], TestClient]) -> TestClient:
    return make_client()


VALID_PROFILE = {
    "birth_year": 1950,
    "birth_month": 6,
    "sex": "female",
    "conditions": ["hypertension"],
}


def register_payload(email: str = "a@example.com", **overrides) -> dict:
    return {"email": email, "password": "correct-horse-battery", **VALID_PROFILE, **overrides}


@pytest.fixture
def login_as(make_client: Callable[[], TestClient]) -> Callable[..., TestClient]:
    """註冊並登入一個新使用者，回傳已帶 session cookie 的客戶端。"""

    def _login(email: str = "a@example.com", **overrides) -> TestClient:
        user_client = make_client()
        response = user_client.post("/api/auth/register", json=register_payload(email, **overrides))
        assert response.status_code == 201, response.text
        return user_client

    return _login
