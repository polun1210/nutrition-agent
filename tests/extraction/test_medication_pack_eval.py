"""藥包 VLM eval 的比對邏輯與 harness（不打外部 API）。"""

import importlib.util
import json
from pathlib import Path

from nutrition_agent.extraction.medication_pack import MedicationPackReading
from nutrition_agent.extraction.medication_pack_eval import PackEvalReport, score_pack

RUN_PY = Path(__file__).resolve().parents[2] / "evals" / "medpack" / "run.py"


def reading(*names):
    return MedicationPackReading(readable=bool(names), names=list(names))


def test_名稱比對忽略大小寫與空白並算召回率與精確率():
    report = PackEvalReport()

    score_pack({"names": ["Amlodipine", "脈優", "Zantac"]}, reading("amlodipine", "脈優", "Lipitor"), report)

    assert (report.gold_names, report.matched_names, report.read_names) == (3, 2, 3)
    assert report.name_recall == 2 / 3 and report.name_precision == 2 / 3


def test_gold_標為讀不到的照片要讀不到才算對():
    report = PackEvalReport()

    score_pack({"names": [], "unreadable": True}, reading(), report)
    score_pack({"names": [], "unreadable": True}, reading("Norvasc"), report)

    assert report.unreadable_correct == (1, 2)


def test_沒有資料時指標是None不報錯():
    summary = PackEvalReport().summary()

    assert summary == {"name_recall": None, "name_precision": None, "unreadable_accuracy": None}


def load_run():
    spec = importlib.util.spec_from_file_location("medpack_run", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harness_在沒有_gold_時能跑空集合(tmp_path, capsys):
    gold, recorded = tmp_path / "gold", tmp_path / "recorded"
    gold.mkdir()
    recorded.mkdir()

    code = load_run().main(["--gold", str(gold), "--recorded", str(recorded), "--json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["name_recall"] is None


def test_harness_重播錄製回應並略過沒有錄製的照片(tmp_path, capsys):
    gold, recorded = tmp_path / "gold", tmp_path / "recorded"
    gold.mkdir()
    recorded.mkdir()
    (gold / "m01.json").write_text(json.dumps({"image_id": "m01", "names": ["Norvasc", "Lipitor"]}), "utf-8")
    (gold / "m02.json").write_text(json.dumps({"image_id": "m02", "names": ["Zantac"]}), "utf-8")
    (recorded / "m01.json").write_text(json.dumps({"readable": True, "names": ["Norvasc"]}), "utf-8")

    load_run().main(["--gold", str(gold), "--recorded", str(recorded), "--json"])

    assert json.loads(capsys.readouterr().out)["name_recall"] == 0.5
