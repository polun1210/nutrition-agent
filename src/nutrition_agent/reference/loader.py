"""載入 data/ 下的參考資料，回傳型別明確的唯讀物件。"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from nutrition_agent.reference.ingredients import IngredientCatalog

DATA_DIR = Path(__file__).parent / "data"


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


class ReferenceData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    ingredients: IngredientCatalog

    @property
    def versions(self) -> dict[str, str]:
        return {"ingredients": self.ingredients.version}


def load_reference_data(data_dir: Path = DATA_DIR) -> ReferenceData:
    manifest = read_toml(data_dir / "manifest.toml")
    raw = read_toml(data_dir / "ingredients.toml")
    ingredients = IngredientCatalog(version=raw["version"], ingredients=raw["ingredient"])
    return ReferenceData(version=manifest["version"], ingredients=ingredients)
