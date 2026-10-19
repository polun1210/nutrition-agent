"""規則說明文字的「不得含數字」檢查。

禁止的是量值數字；成分與用藥名稱本身帶的數字（維生素 B12、n-3、Q10、COX-2）不算。
檢查前先把目錄裡的名稱從文字中移除，再看剩下的有沒有數字。
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_TOKEN = re.compile(r"[a-z]+-?\d+")


def _fold(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


@lru_cache(maxsize=1)
def _names_with_digits() -> tuple[str, ...]:
    with (_DATA_DIR / "ingredients.toml").open("rb") as f:
        ingredients = tomllib.load(f)["ingredient"]
    with (_DATA_DIR / "drugs.toml").open("rb") as f:
        drugs = tomllib.load(f)
    raw = [
        *(n for i in ingredients for n in (i["display_name_zh"], *i.get("synonyms", ()))),
        *(c["name_zh"] for c in drugs["class"]),
        *(n for i in drugs["ingredient"] for n in (i["name_en"], i["name_zh"])),
    ]
    folded = {_fold(n) for n in raw}
    # 名稱裡的字母加數字片段（維生素 B12 的 B12、COX-2 選擇性抑制劑的 COX-2）本身也算名稱
    folded |= {m for n in folded for m in _TOKEN.findall(n)}
    # 長的先移除，避免「維生素b12」被「b12」切成殘渣
    return tuple(sorted((n for n in folded if any(ch.isdigit() for ch in n)), key=len, reverse=True))


def contains_quantity_digit(text: str) -> bool:
    remaining = _fold(text)
    for name in _names_with_digits():
        remaining = remaining.replace(name, "")
    return any(ch.isdigit() for ch in remaining)
