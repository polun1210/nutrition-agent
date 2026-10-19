"""藥名對照：藥名 → 有效成分 → 用藥類別，並判定範圍狀態。

兩個入口：`search_drugs`（使用者輸入時的候選）與 `resolve_medication`（送出時以原文重新對照）。
對照只看藥名表，不看使用者的個人資料（慢性病不會過濾藥名）。
"""

from __future__ import annotations

from nutrition_agent.assessment.models import Frozen, Medication, MedicationIngredient, ScopeStatus
from nutrition_agent.reference.drug_names import DrugNameEntry, DrugNameTable, normalize_name
from nutrition_agent.reference.drugs import DrugCatalog

MAX_CANDIDATES = 20
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


def resolve_medication(raw_name: str, table: DrugNameTable, catalog: DrugCatalog) -> Medication:
    """以使用者輸入的原文對照藥名表；查不到就是「無法確認」。"""
    entry = table.lookup(raw_name)
    if entry is None:
        return Medication(
            raw_name=raw_name,
            scope_status="unconfirmed",
            name_zh=None,
            ingredients=[],
            out_of_scope_names=[],
        )
    return _medication(raw_name, entry, catalog)


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
