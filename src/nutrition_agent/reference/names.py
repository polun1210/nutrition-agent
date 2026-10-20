"""LLM 解釋的「不得含數字」檢查（ADR 0001）。

禁止的是量值數字；成分、用藥與病名本身帶的數字（維生素 B12、n-3、Q10、COX-2、第2型糖尿病）不算。
檢查前先把這些名稱從文字中移除，再看剩下的有沒有阿拉伯數字（含全形），
以及中文數字接量詞（一年、兩粒、三個月、百分之十）。中文數字單獨出現（一般、兩者、第二型）不算。
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_TOKEN = re.compile(r"[a-z]+-?\d+")
# 目錄以外、帶阿拉伯數字的名稱（_fold 後的寫法）
_EXTRA_NAMES = ("2型糖尿病", "type2diabetes")
_ZH_QUANTITY = re.compile(
    r"百分之|[〇零一二兩三四五六七八九十百千萬半]+"
    r"(?:年|個月|月|週|周|星期|天|日|小時|鐘頭|分鐘|秒|次|粒|顆|錠|膠囊|包|匙|毫克|微克|公克|克|毫升|公升|國際單位|倍|成|%)"
)


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
    folded = {_fold(n) for n in (*raw, *_EXTRA_NAMES)}
    # 名稱裡的字母加數字片段（維生素 B12 的 B12、COX-2 選擇性抑制劑的 COX-2）本身也算名稱
    folded |= {m for n in folded for m in _TOKEN.findall(n)}
    # 長的先移除，避免「維生素b12」被「b12」切成殘渣
    return tuple(sorted((n for n in folded if any(ch.isdigit() for ch in n)), key=len, reverse=True))


def contains_quantity(text: str) -> bool:
    remaining = _fold(text)
    for name in _names_with_digits():
        remaining = remaining.replace(name, "")
    return any(ch.isdigit() for ch in remaining) or _ZH_QUANTITY.search(remaining) is not None
