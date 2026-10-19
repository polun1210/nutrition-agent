from pathlib import Path

import pytest

from nutrition_agent.retrieval.ingest import ingest_corpus
from tests.retrieval.fakes import BagOfWordsGateway

B64 = "![x](data:image/png;base64," + "QUJD" * 200 + ")"

CALCIUM = """# Calcium

## Introduction

Calcium builds bones.

## Interactions with Medications

### Levothyroxine

Calcium carbonate may reduce levothyroxine absorption. Separate doses by 4 hours.
"""


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    _write(tmp_path, "sources/nih_ods/Calcium-HealthProfessional.md", CALCIUM)
    _write(
        tmp_path,
        "sources/nih_ods/Calcium-Consumer-.md",
        "# Calcium\n\n## Intro\n\nMilk has calcium.\n",
    )
    return tmp_path


def _rows(db, where="true", params=()):
    return db.execute(
        "SELECT id, source_type, document_name, document_path, ingredients, section, "
        "start_line, end_line, text FROM evidence_chunk WHERE " + where + " ORDER BY id",
        params,
    ).fetchall()


def test_ingest_records_metadata_traceable_to_source_file(db, knowledge):
    ingest_corpus(db, BagOfWordsGateway(), knowledge)

    rows = _rows(
        db,
        "section = %s AND source_type = %s",
        ("Interactions with Medications > Levothyroxine", "nih_ods_health_professional"),
    )
    assert len(rows) == 1
    _id, _type, name, path, ingredients, _section, start_line, end_line, text = rows[0]
    assert name == "Calcium-HealthProfessional.md"
    assert path == "sources/nih_ods/Calcium-HealthProfessional.md"
    assert ingredients == ["calcium"]
    lines = (knowledge / path).read_text(encoding="utf-8").splitlines()
    assert "\n".join(lines[start_line - 1 : end_line]) == text


def test_consumer_edition_is_a_separate_source_type(db, knowledge):
    ingest_corpus(db, BagOfWordsGateway(), knowledge)
    types = {r[1] for r in _rows(db)}
    assert types == {"nih_ods_health_professional", "nih_ods_consumer"}


def test_rerun_is_idempotent_and_does_not_reembed(db, knowledge):
    ingest_corpus(db, BagOfWordsGateway(), knowledge)
    before = _rows(db)

    second = BagOfWordsGateway()
    result = ingest_corpus(db, second, knowledge)

    assert _rows(db) == before
    assert second.embedded == []
    assert result.added == 0


def test_new_document_is_added_on_rerun(db, knowledge):
    ingest_corpus(db, BagOfWordsGateway(), knowledge)
    count = len(_rows(db))
    _write(
        knowledge,
        "sources/nih_ods/Zinc-HealthProfessional.md",
        "# Zinc\n\n## Interactions with Medications\n\nZinc binds quinolones.\n",
    )

    result = ingest_corpus(db, BagOfWordsGateway(), knowledge)

    assert result.added == 1
    assert len(_rows(db)) == count + 1
    assert _rows(db, "ingredients = %s", (["zinc"],))


def test_changed_document_replaces_stale_chunks(db, knowledge):
    ingest_corpus(db, BagOfWordsGateway(), knowledge)
    _write(
        knowledge,
        "sources/nih_ods/Calcium-HealthProfessional.md",
        CALCIUM.replace("4 hours", "6 hours"),
    )

    ingest_corpus(db, BagOfWordsGateway(), knowledge)

    texts = [r[8] for r in _rows(db, "document_name = %s", ("Calcium-HealthProfessional.md",))]
    assert any("6 hours" in t for t in texts)
    assert not any("4 hours" in t for t in texts)


def test_tfda_keeps_one_representative_label_per_active_ingredient(db, tmp_path):
    base = "raw/tfda/高血脂/Atorvastatin"
    _write(tmp_path, f"{base}/AAA001_20240101.md", "【交互作用】\n舊版仿單：與葡萄柚汁併用。\n")
    _write(
        tmp_path,
        f"{base}/BBB002_20250601.md",
        f"【交互作用】\n新版仿單：與葡萄柚汁併用。\n{B64}\n",
    )
    _write(tmp_path, "raw/tfda/高血壓/Losartan/CCC003_20250101.md", "【交互作用】\n與鉀鹽併用。\n")

    ingest_corpus(db, BagOfWordsGateway(), tmp_path)

    rows = _rows(db, "source_type = 'tfda'")
    assert {r[3] for r in rows} == {
        f"{base}/BBB002_20250601.md",
        "raw/tfda/高血壓/Losartan/CCC003_20250101.md",
    }
    assert {tuple(r[4]) for r in rows} == {("atorvastatin",), ("losartan",)}
    assert not any("base64" in r[8] for r in rows)
    assert all(r[5] == "交互作用" for r in rows)


def test_nccih_folder_is_optional_and_used_when_present(db, tmp_path):
    ingest_corpus(db, BagOfWordsGateway(), tmp_path)
    assert _rows(db) == []

    _write(tmp_path, "sources/nccih/Omega3.md", "# Omega-3\n\n## Side Effects\n\nMay thin blood.\n")
    ingest_corpus(db, BagOfWordsGateway(), tmp_path)
    assert [r[1] for r in _rows(db)] == ["nccih"]


def test_nul_in_source_becomes_replacement_char_not_silently_dropped(db, tmp_path):
    # 仿單轉檔時「≧」等符號可能變成 NUL；直接刪掉會把「≧2.0」變成「2.0」，改成替代字元標示此處有缺字。
    _write(tmp_path, "sources/nih_ods/Zinc-HealthProfessional.md", "# Zinc\n\n## Intro\n\nMIC \x002 mcg/mL\n")

    ingest_corpus(db, BagOfWordsGateway(), tmp_path)

    texts = [row[-1] for row in _rows(db)]
    assert any("MIC \ufffd2 mcg/mL" in t for t in texts)
    assert not any("\x00" in t for t in texts)
