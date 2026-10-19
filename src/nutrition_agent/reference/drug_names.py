"""藥名表：品名（中文／英文）→ 有效成分代碼（複方一對多）。

檔案格式（CSV，UTF-8）：`#` 開頭為註解；第一列 `version,<快照日期>`；
第二列欄位名 `name,lang,ingredients,out_of_scope`。
`ingredients` 為範圍內有效成分代碼，多個以 `|` 分隔；
`out_of_scope` 為對照不到範圍內有效成分的成分名稱（已正規化），同樣以 `|` 分隔。
"""

from __future__ import annotations

import csv
import io
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from nutrition_agent.reference.checks import Violation
    from nutrition_agent.reference.drugs import DrugCatalog

DATA_DIR = Path(__file__).parent / "data"
FULL_TABLE = "drug_names.csv"  # 開發者用 TFDA 匯出腳本產生；存在時優先採用
SAMPLE_TABLE = "drug_names_sample.csv"  # repo 內的小量夾具
COLUMNS = ("name", "lang", "ingredients", "out_of_scope")
_SEPARATOR = "|"
_BANNED_NAMES = ("ranitidine", "雷尼替丁")  # NDMA 汙染已全球下架


def normalize_name(text: str) -> str:
    """NFKC、忽略大小寫、壓縮空白。"""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class DrugNameEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    lang: Literal["zh", "en"]
    ingredients: tuple[str, ...]
    out_of_scope: tuple[str, ...] = ()


class DrugNameTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    entries: tuple[DrugNameEntry, ...]

    @model_validator(mode="before")
    @classmethod
    def _canonical_order(cls, data: object) -> object:
        """依正規化品名排序，讓寫出再載入的表相等、輸出檔可比對差異。"""
        if isinstance(data, dict) and "entries" in data:
            def key(e: object) -> str:
                return normalize_name(e["name"] if isinstance(e, dict) else e.name)

            return {**data, "entries": sorted(data["entries"], key=key)}
        return data

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        keys = [normalize_name(e.name) for e in self.entries]
        if len(set(keys)) != len(keys):
            raise ValueError("藥名表的品名（正規化後）重複")
        return self

    def lookup(self, name: str) -> DrugNameEntry | None:
        key = normalize_name(name)
        return next((e for e in self.entries if normalize_name(e.name) == key), None)


def write_drug_names(table: DrugNameTable, path: Path) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["version", table.version])
    writer.writerow(COLUMNS)
    for e in sorted(table.entries, key=lambda e: normalize_name(e.name)):
        writer.writerow(
            [e.name, e.lang, _SEPARATOR.join(e.ingredients), _SEPARATOR.join(e.out_of_scope)]
        )
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def read_drug_names(path: Path) -> DrugNameTable:
    with path.open(encoding="utf-8", newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    rows = list(csv.reader(lines))
    if rows[0][0] != "version":
        raise ValueError(f"{path.name}: 第一列必須是 version")
    if tuple(rows[1]) != COLUMNS:
        raise ValueError(f"{path.name}: 欄位必須是 {COLUMNS}")
    entries = [
        DrugNameEntry(
            name=name,
            lang=lang,
            ingredients=tuple(filter(None, ingredients.split(_SEPARATOR))),
            out_of_scope=tuple(filter(None, out_of_scope.split(_SEPARATOR))),
        )
        for name, lang, ingredients, out_of_scope in rows[2:]
    ]
    return DrugNameTable(version=rows[0][1], entries=entries)


def check_drug_names(table: DrugNameTable, catalog: DrugCatalog) -> list[Violation]:
    """藥名表的完整性檢查：有效成分必須在目錄內，Ranitidine 不得在範圍內。"""
    from nutrition_agent.reference.checks import Violation

    known = {i.code for i in catalog.ingredients}
    found: list[Violation] = []
    for entry in table.entries:
        for code in entry.ingredients:
            if code not in known:
                found.append(Violation("unknown_ingredient", entry.name, f"有效成分不在目錄：{code}"))
            if any(b in code.casefold() for b in _BANNED_NAMES):
                found.append(
                    Violation("ranitidine_in_scope", entry.name, "Ranitidine 已下架，不得列入範圍")
                )
    return found


def load_drug_names(data_dir: Path = DATA_DIR) -> DrugNameTable:
    """載入藥名表：有完整匯出檔就用它，否則退回 repo 內的小量夾具。"""
    full = data_dir / FULL_TABLE
    return read_drug_names(full if full.exists() else data_dir / SAMPLE_TABLE)


def load_sample_drug_names(data_dir: Path = DATA_DIR) -> DrugNameTable:
    """repo 內的小量夾具；測試與 e2e 用它，結果不受完整匯出檔影響。"""
    return read_drug_names(data_dir / SAMPLE_TABLE)
