"""報告問答 eval：合成個案 → 真聊天模型回答 → 印出工具呼叫順序、回答與來源，由人工判讀（不打分數）。

  離線檢查題目檔（不打 API、不連資料庫）：個案能通過判定引擎，每個題目欄位齊全：
      uv run python evals/report_chat/run.py --dry-run
  打真模型（需要 .env 的 OPENROUTER_*、CHAT_MODEL、DATABASE_URL，且資料庫已 ingest 語料）：
      uv run python evals/report_chat/run.py --live [--only q1-interaction]
  資料庫只讀（檢索與產生報告解釋），不寫入。報告用既有判定引擎與報告模板在記憶體中現算，
  不依賴資料庫裡任何使用者的資料。--live 會呼叫真模型（解釋產生、聊天），會花一點錢。
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("case", "questions"):
        if key not in data:
            raise ValueError(f"題目檔缺少 {key}")
    for q in data["questions"]:
        missing = {"id", "question", "history"} - q.keys()
        if missing:
            raise ValueError(f"題目 {q.get('id')} 缺少欄位 {sorted(missing)}")
    return data


def build_case(raw: dict, ref, table):
    from nutrition_agent.accounts import require_adult
    from nutrition_agent.assessment import AssessmentCase, Product, ProfileSnapshot, assess
    from nutrition_agent.assessment.medications import resolve_medication

    assessed_on = date.fromisoformat(raw["assessed_on"])
    profile = ProfileSnapshot(**raw["profile"])
    case = AssessmentCase(
        profile=profile,
        age=require_adult(profile.birth_year, profile.birth_month, assessed_on),
        assessed_on=assessed_on,
        products=[Product.model_validate(p) for p in raw["products"]],
        medications=[resolve_medication(m, table, ref.drugs) for m in raw["medications"]],
    )
    return case, assess(case, ref)


def _dry_run(data: dict) -> int:
    from nutrition_agent.reference import load_reference_data
    from nutrition_agent.reference.drug_names import load_drug_names

    _, assessment = build_case(data["case"], load_reference_data(), load_drug_names())
    print(
        f"個案可判定：命中交互作用 {len(assessment.interactions)} 條、"
        f"上限比對 {len(assessment.ul_comparisons)} 項"
    )
    for q in data["questions"]:
        print(f"{q['id']}: ok（history {len(q['history'])} 則）")
    return 0 if assessment.interactions else 1


def _live(data: dict, only: str | None) -> int:
    import psycopg

    from nutrition_agent.api.deps import get_chat_model
    from nutrition_agent.config import get_settings
    from nutrition_agent.gateway import OpenRouterGateway
    from nutrition_agent.reference import load_reference_data
    from nutrition_agent.reference.drug_names import load_drug_names
    from nutrition_agent.report_chat.agent import ChatTurn, answer_question
    from nutrition_agent.reporting.explanation import build_explanations
    from nutrition_agent.reporting.template import render_report
    from nutrition_agent.retrieval.search import retrieve_evidence

    settings = get_settings()
    gateway = OpenRouterGateway.from_settings(settings)
    ref = load_reference_data()
    case, assessment = build_case(data["case"], ref, load_drug_names())
    model = get_chat_model()
    print(f"聊天模型：{settings.chat_model}")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.read_only = True  # 只讀：絕不寫入主資料庫
        explanations, footnotes = build_explanations(conn, gateway, assessment, ref)
        report = render_report(case, assessment, ref, explanations, footnotes).model_dump(mode="json")
        assessment_json = assessment.model_dump(mode="json")

        def retrieve(code, drug_codes):
            return retrieve_evidence(conn, gateway, ref, code, drug_codes)

        failed = 0
        for q in data["questions"]:
            if only and q["id"] != only:
                continue
            history = [ChatTurn(m["role"], m["content"]) for m in q["history"]]
            print(f"\n=== {q['id']}（{q.get('covers', '')}）===\n問：{q['question']}")
            try:
                result = answer_question(model, report, assessment_json, q["question"], history, retrieve)
            except Exception as err:  # 人工判讀用：單題失敗不中斷其他題
                print(f"失敗：{type(err).__name__}: {err}")
                failed += 1
                continue
            tools = [
                f"{c.name}({', '.join(f'{k}={v}' for k, v in c.args.items())})"
                for c in result.tool_calls
            ]
            print(f"工具呼叫順序：{' -> '.join(tools) or '（無）'}")
            print(f"答：{result.answer}")
            print(f"來源 {len(result.sources)} 筆：")
            for s in result.sources:
                print(f"  - {s.source_label}｜{s.document_name}｜{s.section}")
    if failed:
        print(f"\n有 {failed} 題失敗")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--cases", type=Path, default=HERE / "cases.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--only", help="只跑指定題目 id")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    data = load_file(args.cases)
    return _dry_run(data) if args.dry_run else _live(data, args.only)


if __name__ == "__main__":
    sys.exit(main())
