"""成分名稱查表：括號只看最外層，內層括號屬於括號裡那個成分。"""

import pytest

from nutrition_agent.extraction.normalize import classify, is_nutrition_fact
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


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("葡萄糖胺鹽酸鹽", "glucosamine"),
        ("結晶型硫酸鹽葡萄糖胺(Crystalline Glucosamine Sulphate)", "glucosamine"),
        ("Glucosamine Sulphate", "glucosamine"),
        ("Glucosamine Sulfate", "glucosamine"),
        ("紅麴粉", "red_yeast_rice"),
        ("紅麴粉末", "red_yeast_rice"),
        ("Concentrated fish Omega-3 triglycerides", "omega_3"),
    ],
)
def test_允許成分的實際標示寫法(catalog, raw, code):
    # 2026-10-20 實拍標示（evals/vlm/gold p01、p07、p08、p23、p26、p27）出現、原本對不到的寫法
    assert classify(raw, catalog) == (code, "in_scope")


@pytest.mark.parametrize(
    "raw", ["熱量", "蛋白質", "脂肪", "飽和脂肪", "反式脂肪", "碳水化合物", "糖", "鈉", "飽和脂肪酸", "熱量(大卡)", "Sodium"]
)
def test_營養標示固定欄位不是成分(raw):
    # 校對頁不顯示這些欄位（#22）
    assert is_nutrition_fact(raw)


@pytest.mark.parametrize("raw", ["乳糖", "蔗糖", "硫酸月桂酯鈉", "Sodium Chloride", "鈣", "膠原蛋白"])
def test_名稱只是含有這些字的成分不算營養標示欄位(raw):
    assert not is_nutrition_fact(raw)
