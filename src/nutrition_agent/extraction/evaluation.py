"""VLM 輸出與金標準（evals/vlm/gold）逐欄位比對。純函數，不打外部 API；evals/vlm/run.py 負責取得讀取結果。"""

import math
from collections import defaultdict
from dataclasses import dataclass, field

from nutrition_agent.extraction.normalize import normalize_unit
from nutrition_agent.extraction.product import ProductExtraction
from nutrition_agent.reference.ingredients import normalize_name

# 金標準的劑型單位 → 本專案的劑型單位
GOLD_DOSE_UNITS = {"tablet": "錠", "capsule": "粒", "softgel": "粒"}
GOLD_UNIT_ALIASES = {"mg_ate": "mg_alpha_te"}

PRODUCT_FIELDS = ("product_name", "serving_size", "dose_unit")
ROW_FIELDS = ("amount", "unit", "scope_status", "standard_code")


@dataclass
class FieldScore:
    correct: int = 0
    total: int = 0

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.total if self.total else None


@dataclass
class EvalReport:
    """各欄位的正確率。row_recall：金標準的列有多少被讀到；row_precision：讀到的列有多少在金標準裡。"""

    fields: dict[str, FieldScore] = field(default_factory=lambda: defaultdict(FieldScore))
    gold_rows: int = 0
    matched_rows: int = 0
    extracted_rows: int = 0

    def add(self, name: str, ok: bool) -> None:
        score = self.fields[name]
        score.total += 1
        score.correct += ok

    @property
    def row_recall(self) -> float | None:
        return self.matched_rows / self.gold_rows if self.gold_rows else None

    @property
    def row_precision(self) -> float | None:
        return self.matched_rows / self.extracted_rows if self.extracted_rows else None

    def summary(self) -> dict[str, float | None]:
        result = {name: self.fields[name].accuracy for name in (*PRODUCT_FIELDS, *ROW_FIELDS)}
        result["row_recall"] = self.row_recall
        result["row_precision"] = self.row_precision
        return result


def _same_number(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-9)


def _row_key(name: str, section: str) -> tuple[str, str]:
    return normalize_name(name), section


def score_product(gold: dict, extraction: ProductExtraction, report: EvalReport) -> None:
    serving = gold["serving_info"]
    report.add("product_name", normalize_name(extraction.product_name or "") == normalize_name(gold["product_name"]))
    report.add("serving_size", _same_number(extraction.units_per_serving, serving.get("serving_size")))
    report.add("dose_unit", extraction.dose_unit == GOLD_DOSE_UNITS.get(serving.get("dose_unit")))

    extracted = {_row_key(r.raw_name, r.section): r for r in extraction.rows}
    report.extracted_rows += len(extracted)
    for gold_row in gold["nutrients"]:
        report.gold_rows += 1
        row = extracted.get(_row_key(gold_row["raw_name"], gold_row["label_section"]))
        if row is None:
            continue
        report.matched_rows += 1
        gold_unit = gold_row.get("unit")
        gold_unit = GOLD_UNIT_ALIASES.get(gold_unit, gold_unit)
        report.add("amount", _same_number(row.amount, gold_row.get("per_serving")))
        report.add("unit", normalize_unit(row.unit) == gold_unit)
        # 金標準只分範圍內／範圍外；我們的「無法確認」對金標準來說也是不進入評估
        ours = "in_scope" if row.scope_status == "in_scope" else "out_of_scope"
        report.add("scope_status", ours == gold_row["scope_status"])
        if ours == "in_scope" or gold_row.get("standard_code"):  # 範圍外的列金標準沒有標準代碼
            report.add("standard_code", row.ingredient_code == gold_row.get("standard_code"))


def format_report(report: EvalReport) -> str:
    lines = []
    for name, value in report.summary().items():
        score = report.fields.get(name)
        detail = f"（{score.correct}/{score.total}）" if score else ""
        text = "n/a" if value is None else f"{value:.1%}"
        lines.append(f"{name:16s} {text:>7s} {detail}")
    return "\n".join(lines)
