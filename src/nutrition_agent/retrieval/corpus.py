"""語料探索：找出 knowledge/ 下要 ingest 的文件，並判定來源類型與成分／有效成分。"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.ingredients import normalize_name

DRIS = "dris"
NIH_ODS_HEALTH_PROFESSIONAL = "nih_ods_health_professional"
NIH_ODS_CONSUMER = "nih_ods_consumer"
NCCIH = "nccih"
TFDA = "tfda"

_DRIS_FILES = ("DRIs_Full.md", "DRIs_Table.md")
_TFDA_FILE = re.compile(r"^(?P<license>.+)_(?P<date>\d{8})\.md$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])")


@dataclass(frozen=True)
class Document:
    source_type: str
    path: Path  # 絕對路徑
    relative_path: str  # 相對 knowledge/，用 / 分隔
    ingredients: tuple[str, ...]  # 文件層級的成分／有效成分代碼；空 = 逐塊判定

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def tag_by_content(self) -> bool:
        return self.source_type == DRIS


def discover_documents(knowledge_dir: Path) -> Iterator[Document]:
    yield from _dris(knowledge_dir)
    yield from _nih_ods(knowledge_dir)
    yield from _nccih(knowledge_dir)
    yield from _tfda(knowledge_dir)


def _relative(knowledge_dir: Path, path: Path) -> str:
    return path.relative_to(knowledge_dir).as_posix()


def _ingredient_code_from_filename(stem: str) -> tuple[str, ...]:
    """`VitaminB12-HealthProfessional` -> vitamin_b12；找不到對應回傳空。"""
    name = _CAMEL_BOUNDARY.sub(" ", stem.split("-")[0])
    found = load_reference_data().ingredients.find(name)
    return (found.code,) if found else ()


def _dris(knowledge_dir: Path) -> Iterator[Document]:
    for name in _DRIS_FILES:
        path = knowledge_dir / "sources" / "dris" / name
        if path.is_file():
            yield Document(DRIS, path, _relative(knowledge_dir, path), ())


def _nih_ods(knowledge_dir: Path) -> Iterator[Document]:
    folder = knowledge_dir / "sources" / "nih_ods"
    for path in sorted(folder.glob("*.md")):
        consumer = "-consumer" in path.stem.lower()
        source_type = NIH_ODS_CONSUMER if consumer else NIH_ODS_HEALTH_PROFESSIONAL
        yield Document(
            source_type,
            path,
            _relative(knowledge_dir, path),
            _ingredient_code_from_filename(path.stem),
        )


def _nccih(knowledge_dir: Path) -> Iterator[Document]:
    folder = knowledge_dir / "sources" / "nccih"
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*.md")):
        yield Document(
            NCCIH, path, _relative(knowledge_dir, path), _ingredient_code_from_filename(path.stem)
        )


def _tfda(knowledge_dir: Path) -> Iterator[Document]:
    """`raw/tfda/<疾病>/<有效成分>/<許可證字號>_<日期>.md`；每個有效成分只取日期最新的一份。"""
    root = knowledge_dir / "raw" / "tfda"
    if not root.is_dir():
        return
    latest: dict[str, tuple[tuple[str, str], Path]] = {}
    for path in root.rglob("*.md"):
        match = _TFDA_FILE.match(path.name)
        if match is None or path.parent == root:
            continue
        code = _drug_code(path.parent.name)
        key = (match["date"], match["license"])
        if code not in latest or key > latest[code][0]:
            latest[code] = (key, path)
    for code in sorted(latest):
        path = latest[code][1]
        yield Document(TFDA, path, _relative(knowledge_dir, path), (code,))


def _drug_code(folder_name: str) -> str:
    """資料夾名稱對照用藥有效成分目錄；目錄外的成分以小寫資料夾名稱當代碼。"""
    key = normalize_name(folder_name)
    for ingredient in load_reference_data().drugs.ingredients:
        if key in {normalize_name(n) for n in (ingredient.code, ingredient.name_en, ingredient.name_zh)}:
            return ingredient.code
    return key
