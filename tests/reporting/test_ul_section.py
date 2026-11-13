"""報告「上限比對」段落：各營養素上限的涵蓋範圍措辭。"""

from nutrition_agent.assessment import assess
from nutrition_agent.reporting.template import render_report
from tests.assessment.conftest import line, make_case, product


def ul_line(ref, code_name: str, *lines) -> str:
    case = make_case(product("綜合", list(lines)))
    report = render_report(case, assess(case, ref), ref)
    section = next(s for s in report.sections if s.key == "ul_comparison")
    return next(text for text in section.lines if text.startswith(code_name))


def test_鐵的上限寫明包含強化食品且實際可能更高(ref):
    text = ul_line(ref, "鐵", line("iron", 10))
    assert "補充劑與強化食品" in text
    assert "實際可能更高" in text
    assert "上限只計算補充劑來源" not in text


def test_鎂的上限寫明包含藥物等所有非食物來源(ref):
    text = ul_line(ref, "鎂", line("magnesium", 100))
    assert "所有非食物來源" in text
    assert "藥物" in text
    assert "實際可能更高" in text


def test_其他營養素的上限仍寫定義上包含飲食(ref):
    text = ul_line(ref, "鋅", line("zinc", 5))
    assert "上限定義上包含飲食" in text


def test_葉酸的上限比對標明是依_DRIs_推導的解讀(ref):
    text = ul_line(ref, "葉酸", line("folate", 400, "ug"))
    assert "解讀" in text


def test_ul_row_carries_numeric_percent_for_the_gauge(ref):
    case = make_case(product("鐵", [line("iron", 20)]))
    report = render_report(case, assess(case, ref), ref)
    section = next(s for s in report.sections if s.key == "ul_comparison")
    row = section.table[0]

    assert row.percent_value is not None
    assert row.percent == f"{round(row.percent_value, 1):g}%"


def test_ul_row_without_known_ul_has_no_numeric_percent(ref):
    case = make_case(product("B12", [line("vitamin_b12", 10, "ug")]))
    report = render_report(case, assess(case, ref), ref)
    rows = next(s for s in report.sections if s.key == "ul_comparison").table
    row = next(r for r in rows if r.percent is None)

    assert row.percent_value is None


def ul_row(ref, *lines):
    case = make_case(product("綜合", list(lines)))
    report = render_report(case, assess(case, ref), ref)
    section = next(s for s in report.sections if s.key == "ul_comparison")
    return section, report


def test_報告的單位用顯示名稱不露出內部代碼(ref):
    section, report = ul_row(ref, line("vitamin_e", 33.5, "mg_alpha_te"), line("selenium", 55, "ug"))
    rows = {r.intake: r for r in section.table}

    assert "33.5 mg α-TE" in rows
    assert rows["33.5 mg α-TE"].ul == "1000 mg α-TE"
    assert "55 µg" in rows
    texts = [t for s in report.sections for t in s.lines] + [r.intake for r in section.table]
    assert not any("mg_alpha_te" in t or " ug" in t for t in texts)
