"""藥名對照：藥名 → 有效成分 → 用藥類別，並判定範圍狀態。

兩個入口：`search_drugs`（使用者輸入時的候選）與 `resolve_medication`（照片讀到的藥名、送出時以原文重新對照）。
TFDA 品名帶劑量與劑型（「Crestor 5mg Film-Coated Tablets」），照片與自由輸入通常只有商品名或學名，
所以 `resolve_medication` 逐字比對不到時改用部分比對，候選的成分都相同才帶入；不同就無法確認，交給使用者從搜尋選。
對照只看藥名表，不看使用者的個人資料（慢性病不會過濾藥名）。
"""

from __future__ import annotations

import re

from nutrition_agent.assessment.models import Frozen, Medication, MedicationIngredient, ScopeStatus
from nutrition_agent.reference.drug_names import DrugNameEntry, DrugNameTable, normalize_name
from nutrition_agent.reference.drugs import DrugCatalog

MAX_CANDIDATES = 20
# TFDA 品名用引號標廠商簡稱（例如 "C.M."），拆開對照時不算藥名
QUOTED = re.compile(r'"[^"]*"|“[^”]*”|「[^」]*」')
MIN_PARTIAL_LENGTH = 2  # 正規化後少於兩個字不做部分比對，避免單一字母或單字誤配
MAX_BRAND_NAMES = 6


class DrugCandidate(Frozen):
    """搜尋候選：對照結果加上同成分的其他品名（台灣常見商品名）。"""

    name: str
    scope_status: ScopeStatus
    name_zh: str | None
    ingredients: list[MedicationIngredient]
    out_of_scope_names: list[str]
    brand_names: list[str]


def _ingredients(entry: DrugNameEntry, catalog: DrugCatalog) -> list[MedicationIngredient]:
    found = []
    for code in entry.ingredients:
        ingredient = next(i for i in catalog.ingredients if i.code == code)
        drug_class = catalog.get_class(ingredient.class_code)
        found.append(
            MedicationIngredient(
                code=code,
                name_en=ingredient.name_en,
                name_zh=ingredient.name_zh,
                class_code=drug_class.code,
                class_name_zh=drug_class.name_zh,
            )
        )
    return found


def _scope_status(entry: DrugNameEntry) -> ScopeStatus:
    return "in_scope" if entry.ingredients else "out_of_scope"


def _name_zh(entry: DrugNameEntry, ingredients: list[MedicationIngredient]) -> str | None:
    if entry.lang == "zh":
        return entry.name
    return "、".join(i.name_zh for i in ingredients) or None


def _medication(raw_name: str, entry: DrugNameEntry, catalog: DrugCatalog) -> Medication:
    ingredients = _ingredients(entry, catalog)
    return Medication(
        raw_name=raw_name,
        scope_status=_scope_status(entry),
        name_zh=_name_zh(entry, ingredients),
        ingredients=ingredients,
        out_of_scope_names=list(entry.out_of_scope),
    )


def _same_ingredients(entries: list[DrugNameEntry]) -> list[DrugNameEntry] | None:
    """候選的有效成分組合都相同才回傳；沒有候選或組合不只一種回傳 None。"""
    if not entries or len({frozenset(e.ingredients) for e in entries}) != 1:
        return None
    return entries


def _match(name: str, table: DrugNameTable) -> list[DrugNameEntry] | None:
    entry = table.lookup(name)
    if entry is not None:
        return [entry]
    if len(normalize_name(name)) < MIN_PARTIAL_LENGTH:
        return None
    # 開頭符合的優先：「脈優」不該被「脂脈優」「舒脈優」這類複方拖成無法確認（#20）
    return _same_ingredients(table.starting_with(name) or table.containing(name))


def _match_parts(raw_name: str, table: DrugNameTable) -> list[DrugNameEntry] | None:
    """「金舒胃得 Gisowed」這類中英文寫在一起的藥名：拆開各自對照，對到的部分成分都相同才採用。"""
    parts = QUOTED.sub(" ", raw_name).split()
    if len(parts) < 2:
        return None
    matched = [found for part in parts if (found := _match(part, table))]
    return _same_ingredients([e for found in matched for e in found])


def _partial_medication(raw_name: str, entries: list[DrugNameEntry], catalog: DrugCatalog) -> Medication:
    ingredients = _ingredients(entries[0], catalog)
    # 範圍外成分只列所有候選都有的，不替使用者沒吃的劑型多報
    common = [n for n in entries[0].out_of_scope if all(n in e.out_of_scope for e in entries[1:])]
    return Medication(
        raw_name=raw_name,
        scope_status=_scope_status(entries[0]),
        name_zh="、".join(i.name_zh for i in ingredients) or None,
        ingredients=ingredients,
        out_of_scope_names=common,
    )


def resolve_medication(raw_name: str, table: DrugNameTable, catalog: DrugCatalog) -> Medication:
    """以原文對照藥名表：逐字相符 → 部分比對 → 拆開各自對照；都對不到就是「無法確認」。"""
    entry = table.lookup(raw_name)
    if entry is not None:
        return _medication(raw_name, entry, catalog)
    entries = _match(raw_name, table) or _match_parts(raw_name, table)
    if entries is not None:
        return _partial_medication(raw_name, entries, catalog)
    return Medication(
        raw_name=raw_name,
        scope_status="unconfirmed",
        name_zh=None,
        ingredients=[],
        out_of_scope_names=[],
    )


def _rank(entry: DrugNameEntry, query: str) -> int | None:
    name = normalize_name(entry.name)
    if name == query:
        return 0
    if name.startswith(query):
        return 1
    return 2 if query in name else None


def search_drugs(
    query: str, table: DrugNameTable, catalog: DrugCatalog, limit: int = MAX_CANDIDATES
) -> list[DrugCandidate]:
    """部分比對藥名（中文、英文、商品名皆可），完全相符與前綴優先。"""
    key = normalize_name(query)
    if not key:
        return []
    ranked = [(r, e) for e in table.entries if (r := _rank(e, key)) is not None]
    ranked.sort(key=lambda pair: (pair[0], normalize_name(pair[1].name)))
    candidates = []
    for _, entry in ranked[:limit]:
        medication = _medication(entry.name, entry, catalog)
        siblings = [
            e.name
            for e in table.entries
            if e.ingredients and e.ingredients == entry.ingredients and e.name != entry.name
        ]
        candidates.append(
            DrugCandidate(
                name=entry.name,
                scope_status=medication.scope_status,
                name_zh=medication.name_zh,
                ingredients=medication.ingredients,
                out_of_scope_names=medication.out_of_scope_names,
                brand_names=siblings[:MAX_BRAND_NAMES],
            )
        )
    return candidates
