"""Playwright 煙霧測試用的後端：重建獨立資料庫、跑 migration、啟動 API。

用法（由 web/playwright.config.ts 呼叫）：
    uv run python scripts/e2e_server.py [port]
資料庫連線取自 E2E_DATABASE_URL，預設 nutrition_e2e（需要本機 db 已啟動：docker compose up -d db）。
"""

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")  # 須在 import app 之前

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from moto import mock_aws
from psycopg import conninfo, sql

from nutrition_agent.api.app import create_app
from nutrition_agent.api.assessments import get_drug_names, get_reference
from nutrition_agent.config import get_settings, to_sqlalchemy_url
from nutrition_agent.extraction import medication_pack
from nutrition_agent.photos import PhotoStore, make_s3_client
from nutrition_agent.reference import load_reference_data, load_rule_set
from nutrition_agent.reference.drug_names import load_sample_drug_names

MEDICATION_PACK_REPLY = '{"readable": true, "names": ["Amlodipine", "Zantac"]}'
ROOT = Path(__file__).resolve().parents[1]
RECORDED_VLM = ROOT / "evals" / "vlm" / "recorded" / "vlm"
# 煙霧測試用測試夾具的審定規則（metformin × 維生素 B12），不受真實規則審查結果影響。
FIXTURE_RULES = ROOT / "tests" / "fixtures" / "rules.toml"
EVIDENCE_ID = "ev-e2e0000000000001"
EVIDENCE_TEXT = "Metformin might reduce the absorption of vitamin B12 and reduce serum concentrations."


class RecordedVlmGateway:
    """煙霧測試用的假模型閘道：標示照片回錄製的 p01 辨識結果，藥包照片回固定的兩個藥名，不打外部 API。"""

    def vision(self, prompt: str, image: bytes, mime_type: str) -> str:
        if prompt == medication_pack.PROMPT:  # 藥包照片：固定回兩個藥名
            return MEDICATION_PACK_REPLY
        return (RECORDED_VLM / "p01-img01.json").read_text(encoding="utf-8")

    def complete(self, prompt: str, system: str | None = None) -> str:
        match = re.search(r"ev-[0-9a-f]+", prompt)
        if match is None:
            return "fake-completion"
        return json.dumps(
            [{"text": "這個藥可能影響維生素 B12 的吸收。", "evidence_ids": [match.group()]}],
            ensure_ascii=False,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

DEFAULT_URL = "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition_e2e"
# 煙霧測試不需要真的 SeaweedFS：照片物件存在 moto 的記憶體 S3。
E2E_S3_ENDPOINT = "http://seaweedfs.e2e:8333"


def check_database_name(url: str) -> str:
    """只允許名稱含 `_e2e` 或以 `nutrition_e2e` 開頭的資料庫被 DROP，避免誤刪開發／正式資料。"""
    name = conninfo.conninfo_to_dict(url)["dbname"]
    if "_e2e" not in name and not name.startswith("nutrition_e2e"):
        raise SystemExit(f"拒絕重建資料庫 {name!r}：e2e 專用資料庫名稱須含 _e2e")
    return name


def recreate_database(url: str) -> None:
    name = check_database_name(url)
    admin = conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    url = os.environ.get("E2E_DATABASE_URL", DEFAULT_URL)
    recreate_database(url)
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()  # import app 時已用預設連線建立過設定
    config = Config("alembic.ini")
    config.attributes["url"] = to_sqlalchemy_url(url)
    command.upgrade(config, "head")
    with psycopg.connect(url) as conn:
        conn.execute(
            "INSERT INTO evidence_chunk (id, source_type, document_name, document_path, ingredients,"
            " section, start_char, end_char, start_line, end_line, text, embedding)"
            " VALUES (%s, 'nih_ods_health_professional', 'VitaminB12-HealthProfessional.md',"
            " 'sources/nih_ods/VitaminB12-HealthProfessional.md', %s, 'Interactions with Medications',"
            " 0, 100, 1, 2, %s, '[0,0,0,0]')",
            (EVIDENCE_ID, ["vitamin_b12", "metformin"], EVIDENCE_TEXT),
        )
    ref = load_reference_data().model_copy(update={"rules": load_rule_set(FIXTURE_RULES)})
    os.environ["MOTO_S3_CUSTOM_ENDPOINTS"] = E2E_S3_ENDPOINT
    mock_aws().start()  # 不停止：行程結束就清掉，uvicorn 的執行緒都看得到
    # 縮圖導向的網址瀏覽器連不到（moto 只在行程內），煙霧測試只看縮圖元素在不在。
    client = make_s3_client(E2E_S3_ENDPOINT, "e2e", "e2e", "us-east-1")
    store = PhotoStore(client, "photos", client, 900)
    app = create_app(gateway=RecordedVlmGateway(), photo_store=store)  # bucket 由 lifespan 建
    app.dependency_overrides[get_reference] = lambda: ref
    sample = load_sample_drug_names()
    app.dependency_overrides[get_drug_names] = lambda: sample
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
