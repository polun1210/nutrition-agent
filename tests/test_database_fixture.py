"""測試資料庫沒開時：用到資料庫的測試幾秒內就以明確提示失敗，純函數測試照常通過。"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 沒有服務在聽的埠。沒有短逾時的話，Windows 上要等 psycopg 預設的 130 秒才報錯。
UNREACHABLE_URL = "postgresql://nutrition:nutrition@127.0.0.1:1/nutrition_test_unreachable"
# 含子行程啟動與 import 的時間；超過就代表沒有快速失敗。
FAIL_FAST_SECONDS = 30


def test_unreachable_database_fails_fast_with_hint_and_pure_tests_still_pass() -> None:
    env = {**os.environ, "TEST_DATABASE_URL": UNREACHABLE_URL, "PYTHONUTF8": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            "tests/test_smoke.py::test_package_imports",  # 純函數測試，不用資料庫
            "tests/test_migrations.py::test_遷移後已啟用_pgvector",  # 用到資料庫
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=FAIL_FAST_SECONDS,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "127.0.0.1:1" in output
    assert "docker compose up -d db" in output
    assert "1 passed" in output
    assert "1 error" in output
