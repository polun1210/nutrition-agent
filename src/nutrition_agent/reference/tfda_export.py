"""由 TFDA 藥品開放資料產生藥名表。

輸入為 TFDA 開放資料平台（https://data.fda.gov.tw）的兩個 CSV：
- 藥品許可證資料集：用到欄位 許可證字號、註銷狀態、有效日期、中文品名、英文品名。
- 藥品處方成分資料集：用到欄位 許可證字號、處方標示、成分名稱。
欄位名稱依開放資料平台公開的資料集欄位說明；若平台改欄名，改下面的 `*_COL` 常數即可，
缺欄位時會直接報錯而不是默默產出空表。

執行：`uv run python -m nutrition_agent.reference.tfda_export 許可證.csv 處方成分.csv 輸出.csv --snapshot 2026-10-01`
"""

from __future__ import annotations

import argparse
import csv
import tomllib
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from nutrition_agent.reference.drug_names import (
    DrugNameEntry,
    DrugNameTable,
    normalize_name,
    write_drug_names,
)

ALIASES_PATH = Path(__file__).parent / "data" / "drug_ingredient_aliases.toml"

PERMIT_ID_COL = "許可證字號"
STATUS_COL = "註銷狀態"
EXPIRY_COL = "有效日期"
NAME_ZH_COL = "中文品名"
NAME_EN_COL = "英文品名"
FORMULA_KIND_COL = "處方標示"
INGREDIENT_COL = "成分名稱"

# 官方「註銷狀態」實際值：空白（有效）、已註銷、已廢止；沒有「未註銷」這個值。
# fail-closed：只有空白才算有效，任何其他值（含未知值）一律排除。
_ACTIVE_STATUS = ""


def load_aliases(path: Path = ALIASES_PATH) -> dict[str, str]:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return {normalize_name(k): v for k, v in raw["alias"].items()}


def _read_rows(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: 缺少欄位 {sorted(missing)}")
        return list(reader)


def _parse_date(text: str) -> date:
    return date.fromisoformat(text.strip().replace("/", "-"))


def _is_valid_permit(row: dict[str, str], snapshot_date: date) -> bool:
    if row[STATUS_COL].strip() != _ACTIVE_STATUS:
        return False
    return _parse_date(row[EXPIRY_COL]) >= snapshot_date


def _ingredients_by_permit(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        # 「處方標示」是自由文字（官方資料約 6,936 種），不是穩定的主成分／賦形劑分類，
        # 沒有官方語意可據以排除，所以不使用；賦形劑只會多出範圍外成分（保守方向）。
        name = normalize_name(row[INGREDIENT_COL])
        if name:
            result[row[PERMIT_ID_COL].strip()].append(name)
    return result


def export_drug_names(
    permits_csv: Path,
    ingredients_csv: Path,
    *,
    snapshot_date: date,
    aliases: dict[str, str] | None = None,
) -> DrugNameTable:
    """只納入有效許可證（註銷狀態空白且有效日期未過）；成分經成分對照表對到有效成分，對不上的記為範圍外。"""
    alias_map = load_aliases() if aliases is None else aliases
    permits = _read_rows(permits_csv, [PERMIT_ID_COL, STATUS_COL, EXPIRY_COL, NAME_ZH_COL, NAME_EN_COL])
    by_permit = _ingredients_by_permit(
        _read_rows(ingredients_csv, [PERMIT_ID_COL, FORMULA_KIND_COL, INGREDIENT_COL])
    )

    merged: dict[str, tuple[DrugNameEntry, set[str], set[str]]] = {}
    for row in permits:
        if not _is_valid_permit(row, snapshot_date):
            continue
        names = by_permit.get(row[PERMIT_ID_COL].strip(), [])
        in_scope = {alias_map[n] for n in names if n in alias_map}
        out_scope = {n for n in names if n not in alias_map}
        for column, lang in ((NAME_ZH_COL, "zh"), (NAME_EN_COL, "en")):
            name = row[column].strip()
            if not name:
                continue
            key = normalize_name(name)
            _, known_in, known_out = merged.get(key, (None, set(), set()))
            entry = DrugNameEntry(name=name, lang=lang, ingredients=())
            merged[key] = (entry, known_in | in_scope, known_out | out_scope)

    entries = [
        entry.model_copy(
            update={"ingredients": tuple(sorted(ins)), "out_of_scope": tuple(sorted(outs))}
        )
        for entry, ins, outs in merged.values()
    ]
    return DrugNameTable(version=snapshot_date.isoformat(), entries=entries)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="由 TFDA 開放資料匯出藥名表")
    parser.add_argument("permits_csv", type=Path)
    parser.add_argument("ingredients_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--snapshot", type=date.fromisoformat, required=True, help="資料快照日期 YYYY-MM-DD")
    args = parser.parse_args(argv)
    table = export_drug_names(args.permits_csv, args.ingredients_csv, snapshot_date=args.snapshot)
    write_drug_names(table, args.output)
    print(f"已匯出 {len(table.entries)} 筆品名，版本 {table.version} -> {args.output}")


if __name__ == "__main__":
    main()
