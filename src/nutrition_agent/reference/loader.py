"""載入 data/ 下的參考資料，回傳型別明確的唯讀物件。"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from nutrition_agent.reference.dris import DriTable
from nutrition_agent.reference.drugs import DrugCatalog
from nutrition_agent.reference.ingredients import IngredientCatalog
from nutrition_agent.reference.rules import RuleSet
from nutrition_agent.reference.units import UnitConversions

DATA_DIR = Path(__file__).parent / "data"


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def read_dris_csv(path: Path) -> DriTable:
    """CSV：`#` 開頭為註解；第一列 `version,<版本>`；第二列欄位名；空白欄位視為 None。"""
    with path.open(encoding="utf-8", newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    rows = list(csv.reader(lines))
    if rows[0][0] != "version":
        raise ValueError(f"{path.name}: 第一列必須是 version")
    entries = [
        {key: (value or None) for key, value in zip(rows[1], row, strict=True)}
        for row in rows[2:]
    ]
    for entry in entries:
        if entry["sex"] == "any":  # 男女相同
            entry["sex"] = None
    return DriTable(version=rows[0][1], entries=entries)


def load_rule_set(path: Path = DATA_DIR / "rules.toml") -> RuleSet:
    raw = read_toml(path)
    return RuleSet(version=raw["version"], rules=raw.get("rule", []))


class ReferenceData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    ingredients: IngredientCatalog
    drugs: DrugCatalog
    dris: DriTable
    units: UnitConversions
    rules: RuleSet

    @property
    def versions(self) -> dict[str, str]:
        return {
            "ingredients": self.ingredients.version,
            "drugs": self.drugs.version,
            "dris": self.dris.version,
            "units": self.units.version,
            "rules": self.rules.version,
        }


def load_reference_data(data_dir: Path = DATA_DIR) -> ReferenceData:
    manifest = read_toml(data_dir / "manifest.toml")
    raw = read_toml(data_dir / "ingredients.toml")
    ingredients = IngredientCatalog(version=raw["version"], ingredients=raw["ingredient"])
    raw = read_toml(data_dir / "drugs.toml")
    drugs = DrugCatalog(
        version=raw["version"], classes=raw["class"], ingredients=raw["ingredient"]
    )
    raw = read_toml(data_dir / "units.toml")
    units = UnitConversions(version=raw["version"], rules=raw["rule"])
    return ReferenceData(
        version=manifest["version"],
        ingredients=ingredients,
        drugs=drugs,
        dris=read_dris_csv(data_dir / "dris.csv"),
        units=units,
        rules=load_rule_set(data_dir / "rules.toml"),
    )
