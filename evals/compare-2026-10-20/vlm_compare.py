"""VLM 候選比較：每個模型跑保健食品與藥包照片，存讀取結果與每次呼叫秒數；費用取 OpenRouter 用量前後差。

  uv run python evals/compare-2026-10-20/vlm_compare.py <輸出資料夾> <照片資料夾> <模型 ID>...
照片資料夾底下要有 supplements/p*.jpg 與 medpack/m*.jpg。
"""

import csv
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from nutrition_agent.config import Settings, get_settings
from nutrition_agent.extraction import read_label
from nutrition_agent.extraction.medication_pack import read_medication_pack
from nutrition_agent.gateway import OpenRouterGateway

CONCURRENCY = 4
USAGE_SETTLE_SECONDS = 15  # OpenRouter 用量更新有延遲


def usage(settings: Settings) -> float:
    response = httpx.get(
        f"{settings.openrouter_base_url}/key",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        timeout=30,
    )
    return response.json()["data"]["usage"]


def run_job(gateway: OpenRouterGateway, out: pathlib.Path, job: tuple[str, pathlib.Path]) -> tuple:
    kind, path = job
    read = read_label if kind == "vlm" else read_medication_pack
    start = time.monotonic()
    try:
        reading, error = read(gateway, path.read_bytes(), "image/jpeg"), ""
    except Exception as exc:  # 記錄失敗，不中斷整批
        reading, error = None, f"{type(exc).__name__}: {exc}"[:200]
    seconds = round(time.monotonic() - start, 1)
    if reading is not None:
        folder = out / kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{path.stem}.json").write_text(reading.model_dump_json(indent=2), encoding="utf-8")
    return kind, path.stem, seconds, error


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out, photos, models = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3:]
    jobs = [("vlm", p) for p in sorted((photos / "supplements").glob("p*.jpg"))]
    jobs += [("medpack", p) for p in sorted((photos / "medpack").glob("m*.jpg"))]
    settings = get_settings()
    for model in models:
        gateway = OpenRouterGateway.from_settings(settings.model_copy(update={"vlm_model": model}))
        folder = out / model.replace("/", "_")
        before = usage(settings)
        with ThreadPoolExecutor(CONCURRENCY) as pool:
            rows = list(pool.map(lambda job: run_job(gateway, folder, job), jobs))
        time.sleep(USAGE_SETTLE_SECONDS)
        cost = usage(settings) - before
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "timing.csv").open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([("kind", "image", "seconds", "error"), *rows])
        errors = [r for r in rows if r[3]]
        print(f"{model}: {len(rows)} 次、失敗 {len(errors)}、花費 ${cost:.3f}", flush=True)
        for error in errors:
            print("   ", error, flush=True)


if __name__ == "__main__":
    main()
