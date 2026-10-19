"""多張照片的辨識結果合併成一筆產品，預填到校對頁。"""

from pydantic import BaseModel, ConfigDict

from nutrition_agent.extraction.normalize import (
    ScopeStatus,
    classify,
    normalize_dose_unit,
    normalize_unit,
)
from nutrition_agent.extraction.reading import UNREADABLE_HINT, Section, VlmReading
from nutrition_agent.reference import IngredientCatalog


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ExtractedRow(Frozen):
    raw_name: str
    section: Section
    amount: float | None
    unit: str | None
    readable: bool
    ingredient_code: str | None  # None = 目錄查不到
    scope_status: ScopeStatus
    photo_id: int


class PhotoStatus(Frozen):
    photo_id: int
    readable: bool
    hint: str | None


class ProductExtraction(Frozen):
    product_name: str | None
    units_per_serving: float | None
    dose_unit: str | None
    rows: list[ExtractedRow]
    photos: list[PhotoStatus]


def _row(photo_id: int, raw, catalog: IngredientCatalog) -> ExtractedRow:
    code, status = classify(raw.raw_name, catalog)
    readable = raw.readable
    return ExtractedRow(
        raw_name=raw.raw_name,
        section=raw.section,
        amount=raw.amount if readable else None,
        unit=normalize_unit(raw.unit) if readable else None,
        readable=readable,
        ingredient_code=code,
        scope_status=status,
        photo_id=photo_id,
    )


def build_extraction(
    readings: list[tuple[int, VlmReading]], catalog: IngredientCatalog
) -> ProductExtraction:
    """readings 為 (照片編號, 該張的讀取結果)，依上傳順序；同一列重複只留第一次出現。"""
    name: str | None = None
    serving: float | None = None
    dose_unit: str | None = None
    rows: list[ExtractedRow] = []
    seen: set[tuple] = set()
    for photo_id, reading in readings:
        if not reading.readable:
            continue
        name = name or (reading.product_name or "").strip() or None
        serving = serving or reading.serving_size
        dose_unit = dose_unit or normalize_dose_unit(reading.dose_unit)
        for raw in reading.rows:
            row = _row(photo_id, raw, catalog)
            key = (row.raw_name, row.section, row.amount, row.unit)
            if key not in seen:
                seen.add(key)
                rows.append(row)
    photos = [
        PhotoStatus(
            photo_id=photo_id,
            readable=reading.readable,
            hint=None if reading.readable else UNREADABLE_HINT,
        )
        for photo_id, reading in readings
    ]
    return ProductExtraction(
        product_name=name,
        units_per_serving=serving,
        dose_unit=dose_unit,
        rows=rows,
        photos=photos,
    )
