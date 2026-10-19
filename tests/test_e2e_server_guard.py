"""e2e 伺服器重建資料庫前的防呆：不得對非 e2e 資料庫下 DROP。"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "e2e_server.py"


@pytest.fixture(scope="module")
def e2e_server():
    spec = importlib.util.spec_from_file_location("e2e_server", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["nutrition", "postgres", "nutrition_test", "prod_data"])
def test_refuses_non_e2e_database(e2e_server, name: str) -> None:
    url = f"postgresql://u:p@127.0.0.1:55432/{name}"
    with pytest.raises(SystemExit, match="e2e"):
        e2e_server.recreate_database(url)


@pytest.mark.parametrize("name", ["nutrition_e2e", "nutrition_e2e_review", "my_e2e_db"])
def test_accepts_e2e_database_name(e2e_server, name: str) -> None:
    e2e_server.check_database_name(f"postgresql://u:p@127.0.0.1:55432/{name}")
