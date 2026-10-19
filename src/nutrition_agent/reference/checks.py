"""參考資料的完整性檢查：資料一旦壞掉，回傳的違規清單就不是空的。"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from nutrition_agent.reference.compounds import SUPPORTED_NUTRIENTS, evaluate_expression
from nutrition_agent.reference.rules import (
    Citation,
    ConditionType,
    Rule,
    RuleSet,
    SourceType,
)

if TYPE_CHECKING:
    from nutrition_agent.reference.loader import ReferenceData

KNOWLEDGE_DIR = Path(__file__).parents[3] / "knowledge"

# 各出處類型的文件必須放的位置（相對於 knowledge/）。
_NIH_ODS_DIR = "sources/nih_ods/"
_SOURCE_DIRS: dict[SourceType, tuple[str, ...]] = {
    SourceType.TFDA_LABEL: ("processed/tfda/",),  # raw/ 不進版控，引文無法重現
    SourceType.NIH_ODS_HP: (_NIH_ODS_DIR,),
    SourceType.NCCIH: ("sources/nccih/",),
}
_BANNED_DRUG_NAMES = ("ranitidine", "雷尼替丁")  # NDMA 汙染已全球下架


@dataclass(frozen=True)
class Violation:
    code: str
    subject: str
    message: str


def _normalize_text(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split())


@lru_cache(maxsize=64)
def _read_normalized(path: Path) -> str:
    return _normalize_text(path.read_text(encoding="utf-8"))


def _check_citation(rule: Rule, cite: Citation, knowledge_dir: Path) -> list[Violation]:
    subject = rule.id
    doc = cite.document.replace("\\", "/")
    if "consumer" in Path(doc).name.casefold():
        return [Violation("consumer_source", subject, f"不接受 Consumer 版：{doc}")]
    if not doc.startswith(_SOURCE_DIRS[cite.source_type]):
        return [Violation("source_type_mismatch", subject, f"{cite.source_type} 不該引用 {doc}")]
    if cite.source_type is SourceType.NIH_ODS_HP and not doc.endswith("-HealthProfessional.md"):
        return [Violation("source_type_mismatch", subject, f"NIH ODS 只接受 HealthProfessional 版：{doc}")]
    path = knowledge_dir / doc
    if not path.is_file():
        return [Violation("document_missing", subject, f"找不到出處文件：{doc}")]
    if _normalize_text(cite.quote) not in _read_normalized(path):
        return [Violation("quote_not_in_corpus", subject, f"引文不在 {doc} 中：{cite.quote[:40]}")]
    return []


def _check_references(rule: Rule, data: ReferenceData) -> list[Violation]:
    found: list[Violation] = []
    if data.ingredients.get(rule.ingredient_code) is None:
        found.append(Violation("unknown_ingredient", rule.id, f"成分不在目錄：{rule.ingredient_code}"))
    if rule.condition_type is ConditionType.DRUG_CLASS:
        known = {c.code for c in data.drugs.classes}
    else:
        known = {i.code for i in data.drugs.ingredients}
    if rule.condition_code not in known:
        found.append(
            Violation("unknown_condition", rule.id, f"{rule.condition_type} 不在目錄：{rule.condition_code}")
        )
    return found


def _check_scope(data: ReferenceData) -> list[Violation]:
    names = [
        *(c.code for c in data.drugs.classes),
        *(c.name_zh for c in data.drugs.classes),
        *(f"{i.code} {i.name_en} {i.name_zh}" for i in data.drugs.ingredients),
    ]
    banned = (n for n in names for b in _BANNED_DRUG_NAMES if b in n.casefold())
    return [Violation("ranitidine_in_scope", n, "Ranitidine 已下架，不得列入範圍") for n in banned]


_RATIO_TOLERANCE = 5e-5  # element_ratio 四捨五入到小數 4 位


def _check_compounds(data: ReferenceData) -> list[Violation]:
    found: list[Violation] = []
    for c in data.compounds.compounds:
        if c.nutrient_code not in SUPPORTED_NUTRIENTS or data.ingredients.get(c.nutrient_code) is None:
            found.append(
                Violation("compound_nutrient_unsupported", c.code, f"只支援鈣、鎂、鐵：{c.nutrient_code}")
            )
        if not c.molecular_weight_expr.strip() or not c.element_mass_expr.strip():
            found.append(Violation("compound_expr_missing", c.code, "缺少分子量或元素質量計算式"))
            continue
        try:
            ratio = evaluate_expression(c.element_mass_expr) / evaluate_expression(
                c.molecular_weight_expr
            )
        except (ValueError, ZeroDivisionError) as err:
            found.append(Violation("compound_expr_invalid", c.code, str(err)))
            continue
        if abs(ratio - c.element_ratio) > _RATIO_TOLERANCE:
            found.append(
                Violation(
                    "compound_ratio_mismatch",
                    c.code,
                    f"element_ratio {c.element_ratio} 與計算式結果 {ratio:.4f} 不符",
                )
            )
    return found


def check_integrity(
    data: ReferenceData, rules: RuleSet, knowledge_dir: Path = KNOWLEDGE_DIR
) -> list[Violation]:
    """檢查參考資料與規則；回傳空清單代表通過。"""
    violations = _check_scope(data)
    violations.extend(_check_compounds(data))
    for rule_id, count in Counter(r.id for r in rules.rules).items():
        if count > 1:
            violations.append(Violation("duplicate_rule_id", rule_id, "規則 id 重複"))
    for rule in rules.rules:
        violations.extend(_check_references(rule, data))
        for cite in rule.citations:
            violations.extend(_check_citation(rule, cite, knowledge_dir))
    return violations
