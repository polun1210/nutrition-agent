"""藥包 VLM 輸出與金標準（evals/medpack/gold）比對。純函數，不打外部 API。"""

from dataclasses import dataclass

from nutrition_agent.extraction.medication_pack import MedicationPackReading
from nutrition_agent.reference.drug_names import normalize_name


@dataclass
class PackEvalReport:
    """name_recall：金標準的藥名有多少被讀到；name_precision：讀到的藥名有多少在金標準裡。"""

    gold_names: int = 0
    matched_names: int = 0
    read_names: int = 0
    unreadable_total: int = 0
    unreadable_ok: int = 0

    @property
    def name_recall(self) -> float | None:
        return self.matched_names / self.gold_names if self.gold_names else None

    @property
    def name_precision(self) -> float | None:
        return self.matched_names / self.read_names if self.read_names else None

    @property
    def unreadable_correct(self) -> tuple[int, int]:
        return self.unreadable_ok, self.unreadable_total

    def summary(self) -> dict[str, float | None]:
        return {
            "name_recall": self.name_recall,
            "name_precision": self.name_precision,
            "unreadable_accuracy": self.unreadable_ok / self.unreadable_total if self.unreadable_total else None,
        }


def score_pack(gold: dict, reading: MedicationPackReading, report: PackEvalReport) -> None:
    """gold：`{"names": [藥名原文...], "unreadable": 選填 bool}`。"""
    if gold.get("unreadable"):
        report.unreadable_total += 1
        report.unreadable_ok += not reading.readable
        return
    expected = {normalize_name(n) for n in gold["names"]}
    read = {normalize_name(n) for n in reading.names}
    report.gold_names += len(expected)
    report.read_names += len(read)
    report.matched_names += len(expected & read)


def format_pack_report(report: PackEvalReport) -> str:
    lines = []
    for name, value in report.summary().items():
        lines.append(f"{name:20s} {'n/a' if value is None else f'{value:.1%}':>7s}")
    return "\n".join(lines)
