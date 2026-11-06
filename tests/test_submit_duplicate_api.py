"""防止重複送出：循序重送回 409；並行的第二次送出被列鎖擋住，等第一次完成後回 409。"""

import threading
import time
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from nutrition_agent.api.app import create_app
from nutrition_agent.api.assessments import get_drug_names, get_reference
from nutrition_agent.api.deps import get_connection
from nutrition_agent.reference.drug_names import load_sample_drug_names
from tests.assessment.conftest import fx_ref, ref  # noqa: F401
from tests.conftest import register_payload
from tests.fakes import FakeGateway
from tests.test_explanation_api import B12

LOCK_WAIT_SECONDS = 0.8  # 第二次送出若沒被擋住，這段時間內早就完成了
JOIN_TIMEOUT = 10
RACE_EMAIL = "race@example.com"
MEDICATED_DRAFT = {"products": [B12], "medications": [{"name": "Metformin"}]}
CASES_OF_USER = (
    "SELECT count(*) FROM assessment_cases WHERE user_id IN (SELECT id FROM users WHERE email = %s)"
)


@pytest.fixture(autouse=True)
def approved_rules(app, fx_ref):  # noqa: F811
    app.dependency_overrides[get_reference] = lambda: fx_ref


def test_resubmitting_a_submitted_draft_returns_409_and_keeps_one_case(login_as, db):
    client = login_as()
    draft = client.post("/api/assessments/drafts").json()
    client.put(f"/api/assessments/drafts/{draft['id']}", json=MEDICATED_DRAFT)
    url = f"/api/assessments/drafts/{draft['id']}/submit"

    assert client.post(url).status_code == 201
    again = client.post(url)

    assert again.status_code == 409
    assert db.execute(CASES_OF_USER, ("a@example.com",)).fetchone()[0] == 1


class BlockingGateway(FakeGateway):
    """檢索證據時（持有草稿列鎖期間）卡住，直到測試放行。"""

    def __init__(self) -> None:
        super().__init__()
        self.first_embed_started = threading.Event()
        self.release = threading.Event()

    def embed(self, texts):
        self.first_embed_started.set()
        assert self.release.wait(JOIN_TIMEOUT)
        return super().embed(texts)


@pytest.fixture
def committed_app(database_url, photo_store, fx_ref):  # noqa: F811
    """每個請求各開一條獨立連線並真的 commit（不走單一交易的 db 夾具）。"""
    gateway = BlockingGateway()
    app = create_app(gateway=gateway, photo_store=photo_store)

    def own_connection() -> Iterator[psycopg.Connection]:
        with psycopg.connect(database_url) as conn:
            yield conn

    sample = load_sample_drug_names()
    app.dependency_overrides[get_connection] = own_connection
    app.dependency_overrides[get_drug_names] = lambda: sample
    app.dependency_overrides[get_reference] = lambda: fx_ref
    yield app, gateway
    user = "(SELECT id FROM users WHERE email = %s)"
    with psycopg.connect(database_url) as conn:
        conn.execute(f"DELETE FROM assessment_drafts WHERE user_id IN {user}", (RACE_EMAIL,))
        conn.execute(f"DELETE FROM assessment_cases WHERE user_id IN {user}", (RACE_EMAIL,))
        conn.execute("DELETE FROM users WHERE email = %s", (RACE_EMAIL,))


def test_concurrent_second_submit_waits_on_row_lock_then_gets_409(committed_app, database_url):
    app, gateway = committed_app
    with TestClient(app) as setup:
        registered = setup.post("/api/auth/register", json=register_payload(RACE_EMAIL))
        assert registered.status_code == 201
        draft = setup.post("/api/assessments/drafts").json()
        setup.put(f"/api/assessments/drafts/{draft['id']}", json=MEDICATED_DRAFT)
        cookies = dict(setup.cookies)
    url = f"/api/assessments/drafts/{draft['id']}/submit"
    statuses: dict[str, int] = {}

    def submit(name: str) -> None:
        with TestClient(app, cookies=cookies) as browser:
            statuses[name] = browser.post(url).status_code

    first = threading.Thread(target=submit, args=("first",))
    first.start()
    assert gateway.first_embed_started.wait(JOIN_TIMEOUT)  # 第一次已持有列鎖，正在檢索
    second = threading.Thread(target=submit, args=("second",))
    second.start()
    time.sleep(LOCK_WAIT_SECONDS)
    assert "second" not in statuses  # 第二次被列鎖擋住
    gateway.release.set()
    first.join(JOIN_TIMEOUT)
    second.join(JOIN_TIMEOUT)

    assert statuses == {"first": 201, "second": 409}
    with psycopg.connect(database_url) as conn:
        assert conn.execute(CASES_OF_USER, (RACE_EMAIL,)).fetchone()[0] == 1
