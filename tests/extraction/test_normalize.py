"""成分名稱查表：括號只看最外層，內層括號屬於括號裡那個成分。"""

import pytest

from nutrition_agent.extraction.normalize import classify
from nutrition_agent.reference import load_reference_data


@pytest.fixture(scope="module")
def catalog():
    return load_reference_data().ingredients


def test_巢狀括號裡的成分不會蓋過外層成分(catalog):
    raw = "葉黃素(明膠、蔗糖、葉黃素、生育醇(維生素E)(抗氧化劑)、L-抗壞血酸鈉(抗氧化劑))"
    assert classify(raw, catalog) == ("lutein", "out_of_scope")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("乙酸dl-α-生育醇酯(維生素E)(維生素E、辛烯基丁二酸鈉澱粉、二氧化矽)", "vitamin_e"),
        ("氰鈷胺明(維生素B12)(辛烯基丁二酸鈉澱粉、檸檬酸鈉、維生素B12)", "vitamin_b12"),
        ("生物素(磷酸氫鈣(無水)、生物素)", "biotin"),
        ("膽鈣化醇（維生素D3）", "vitamin_d"),
    ],
)
def test_外層括號裡的名稱仍可對到成分(catalog, raw, code):
    assert classify(raw, catalog)[0] == code
