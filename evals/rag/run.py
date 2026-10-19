"""RAG eval：問題 → 預期證據段落 → 預期解釋重點。資料格式見 cases.json 與
src/nutrition_agent/retrieval/evaluation.py。

  離線檢查資料本身（預期原文真的在 knowledge/ 裡，不花錢）：
      uv run python evals/rag/run.py --dry-run
  打真模型（需要 .env 的 OPENROUTER_*、DATABASE_URL，且資料庫已用同一個 embedding 模型 ingest 過語料：
  uv run python -m nutrition_agent.retrieval.ingest）：
      uv run python evals/rag/run.py --live [--limit 8]
  --live 逐筆輸出：預期段落找到幾個、解釋是否通過輸出檢查（或退回模板）、預期重點涵蓋幾個。
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _dry_run(cases, knowledge: Path) -> int:
    from nutrition_agent.retrieval.evaluation import validate_against_corpus

    bad = 0
    for case in cases:
        problems = validate_against_corpus(case, knowledge)
        bad += bool(problems)
        print(f"{case.id}: {'ok' if not problems else '; '.join(problems)}")
    return 1 if bad else 0


def _live(cases, limit: int) -> int:
    import psycopg

    from nutrition_agent.assessment import InteractionFinding, TriggeringDrug
    from nutrition_agent.config import get_settings
    from nutrition_agent.gateway import OpenRouterGateway
    from nutrition_agent.reporting.explanation import explain_finding
    from nutrition_agent.retrieval.evaluation import score_points, score_retrieval
    from nutrition_agent.retrieval.search import retrieve_evidence

    settings = get_settings()
    gateway = OpenRouterGateway.from_settings(settings)
    with psycopg.connect(settings.database_url) as conn:
        for case in cases:
            evidence = retrieve_evidence(
                conn, gateway, case.ingredient_code, case.drug_ingredient_codes, limit=limit
            )
            finding = InteractionFinding(
                ingredient_code=case.ingredient_code,
                supplemented=True,
                rule_ids=[],
                triggering_drugs=[
                    TriggeringDrug(raw_name=c, ingredient_code=c, class_code="")
                    for c in case.drug_ingredient_codes
                ],
                reasons_zh=[],
                advice=["inform_provider"],
                separation_hours=None,
                unit=None,
                supplement_intake=None,
                recommended_total=None,
                ul=None,
            )
            retrieval = score_retrieval(case, evidence)
            sentences = explain_finding(gateway, finding, case.ingredient_code, evidence)
            if sentences is None:
                print(f"{case.id}: 檢索 {retrieval.found}/{retrieval.total}；解釋不合格（會退回模板）")
                continue
            points = score_points(case, "".join(s.text for s in sentences))
            print(
                f"{case.id}: 檢索 {retrieval.found}/{retrieval.total}；解釋合格；"
                f"重點 {points.found}/{points.total}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--cases", type=Path, default=HERE / "cases.json")
    parser.add_argument("--knowledge", type=Path, default=ROOT / "knowledge")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=8, help="每個問題檢索幾個段落")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 主控台預設不是 UTF-8

    from nutrition_agent.retrieval.evaluation import load_cases

    cases = load_cases(args.cases)
    return _dry_run(cases, args.knowledge) if args.dry_run else _live(cases, args.limit)


if __name__ == "__main__":
    sys.exit(main())
