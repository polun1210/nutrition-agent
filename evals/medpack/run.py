"""藥包 VLM eval：VLM 讀出的藥名與 gold 比對，輸出召回率／精確率。

gold 格式（`evals/medpack/gold/<image_id>.json`，由開發者標註；資料夾可以是空的）：
    {"image_id": "m01", "names": ["Norvasc", "脈優"], "ingredients": ["amlodipine"], "unreadable": false}
  names 是照片上看得到的藥名原文（商品名、學名、中文名，不含劑量、廠牌）；ingredients 是這張照片的藥
  應該對到的目錄成分代碼（目錄外的藥是 []），用來算成分指標：讀到的藥名經正式的藥名對照
  （assessment.medications.resolve_medication）後對到哪些成分。
  整張拍壞、本來就該讀不到的照片用 {"image_id": ..., "names": [], "unreadable": true}。
  照片本身不在 repo，檔名 `<image_id>.jpg|png|webp`。

兩種模式：
  重播錄製回應（預設，不花錢；沒有 gold 也能跑，結果是 n/a）：
      uv run python evals/medpack/run.py
  打真模型（需要 .env 的 OPENROUTER_* 與 VLM_MODEL）：
      uv run python evals/medpack/run.py --live --images D:/photos [--save-recorded evals/medpack/recorded]

錄製回應放在 `evals/medpack/recorded/<image_id>.json`（`MedicationPackReading` 的 JSON）。
"""

import argparse
import json
import sys
from pathlib import Path

from nutrition_agent.extraction.medication_pack import (
    MedicationPackReading,
    parse_pack_reading,
    read_medication_pack,
)
from nutrition_agent.extraction.medication_pack_eval import PackEvalReport, format_pack_report, score_pack

HERE = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _replay(directory: Path, image_id: str) -> MedicationPackReading | None:
    path = directory / f"{image_id}.json"
    return parse_pack_reading(path.read_text(encoding="utf-8")) if path.exists() else None


def _live(gateway, images: Path, image_id: str, save_to: Path | None) -> MedicationPackReading | None:
    for suffix, mime in IMAGE_SUFFIXES.items():
        path = images / f"{image_id}{suffix}"
        if path.exists():
            reading = read_medication_pack(gateway, path.read_bytes(), mime)
            if save_to is not None:
                save_to.mkdir(parents=True, exist_ok=True)
                (save_to / f"{image_id}.json").write_text(reading.model_dump_json(indent=2), encoding="utf-8")
            return reading
    return None


def _resolver():
    from nutrition_agent.assessment.medications import resolve_medication
    from nutrition_agent.reference import load_reference_data
    from nutrition_agent.reference.drug_names import load_drug_names

    table, catalog = load_drug_names(), load_reference_data().drugs
    return lambda name: [i.code for i in resolve_medication(name, table, catalog).ingredients]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--gold", type=Path, default=HERE / "gold")
    parser.add_argument("--recorded", type=Path, default=HERE / "recorded")
    parser.add_argument("--live", action="store_true", help="打真模型")
    parser.add_argument("--images", type=Path, help="--live 時的照片資料夾")
    parser.add_argument("--save-recorded", type=Path, help="--live 時把解析結果存成錄製回應")
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

    resolve = _resolver()
    report, skipped = PackEvalReport(), []
    for gold_path in sorted(args.gold.glob("*.json")) if args.gold.exists() else []:
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        image_id = gold.get("image_id", gold_path.stem)
        reading = (
            _live(gateway, args.images, image_id, args.save_recorded)
            if gateway
            else _replay(args.recorded, image_id)
        )
        if reading is None:
            skipped.append(image_id)
            continue
        score_pack(gold, reading, report, resolve)

    if args.json:
        print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
    else:
        print(format_pack_report(report))
        if skipped:
            print(f"略過（沒有{'照片' if gateway else '錄製回應'}）：{', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
