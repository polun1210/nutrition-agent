"""保健食品 VLM eval：VLM 輸出與 gold 逐欄位比對，輸出各欄位正確率。

兩種模式（gold 的 image_id 對應照片檔名，例如 p01-img01）：
  重播錄製回應（預設，不花錢）：
      uv run python evals/vlm/run.py
      uv run python evals/vlm/run.py --recorded evals/vlm/recorded/vlm
  打真模型（需要 .env 的 OPENROUTER_* 與 VLM_MODEL；照片不在 repo，放在 --images 資料夾，
  檔名 <image_id>.jpg/.png/.webp）：
      uv run python evals/vlm/run.py --live --images D:/photos [--save-recorded evals/vlm/recorded/vlm]

只比對有錄製回應／有照片的 image_id；沒有的會列出略過。
"""

import argparse
import json
import sys
from pathlib import Path

from nutrition_agent.extraction import VlmReading, build_extraction, parse_reading, read_label
from nutrition_agent.extraction.evaluation import EvalReport, format_report, score_product
from nutrition_agent.reference import load_reference_data

HERE = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _replay(directory: Path, image_id: str) -> VlmReading | None:
    path = directory / f"{image_id}.json"
    return parse_reading(path.read_text(encoding="utf-8")) if path.exists() else None


def _live(gateway, images: Path, image_id: str, save_to: Path | None) -> VlmReading | None:
    for suffix, mime in IMAGE_SUFFIXES.items():
        path = images / f"{image_id}{suffix}"
        if path.exists():
            reading = read_label(gateway, path.read_bytes(), mime)
            if save_to is not None:
                save_to.mkdir(parents=True, exist_ok=True)
                (save_to / f"{image_id}.json").write_text(
                    reading.model_dump_json(indent=2), encoding="utf-8"
                )
            return reading
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--gold", type=Path, default=HERE / "gold")
    parser.add_argument("--recorded", type=Path, default=HERE / "recorded" / "vlm")
    parser.add_argument("--live", action="store_true", help="打真模型")
    parser.add_argument("--images", type=Path, help="--live 時的照片資料夾")
    parser.add_argument("--save-recorded", type=Path, help="--live 時把原始解析結果存成錄製回應")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 主控台預設不是 UTF-8

    gateway = None
    if args.live:
        if args.images is None:
            parser.error("--live 需要 --images")
        from nutrition_agent.config import get_settings
        from nutrition_agent.gateway import OpenRouterGateway

        gateway = OpenRouterGateway.from_settings(get_settings())

    catalog = load_reference_data().ingredients
    report, skipped = EvalReport(), []
    for gold_path in sorted(args.gold.glob("p*.json")):
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        image_id = gold["source_images"][0]["image_id"]
        reading = (
            _live(gateway, args.images, image_id, args.save_recorded)
            if gateway
            else _replay(args.recorded, image_id)
        )
        if reading is None:
            skipped.append(image_id)
            continue
        score_product(gold, build_extraction([(0, reading)], catalog), report)

    if args.json:
        print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
        if skipped:
            print(f"略過（沒有{'照片' if gateway else '錄製回應'}）：{', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
