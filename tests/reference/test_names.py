"""「不得含數字」檢查：量值數字要擋，名稱裡的數字與一般用語不擋。"""

import pytest

from nutrition_agent.reference.names import contains_quantity


@pytest.mark.parametrize(
    "text",
    [
        "長期服用超過一年可能降低血鎂。",
        "每天兩粒就可能超過上限。",
        "連續使用三個月以上要注意。",
        "約有百分之十的人會出現這種情況。",
        "吸收量可能減少兩倍。",
        "服藥後半小時再吃。",
        "服用２粒",
    ],
)
def test_中文或全形數字加上量詞要擋(text):
    assert contains_quantity(text)


@pytest.mark.parametrize(
    "text",
    [
        "一般來說，兩者一起使用時要留意。",
        "這是同一類藥物，十分常見。",
        "第二型糖尿病患者常用這個藥。",
        "第2型糖尿病患者常用這個藥。",
        "這個藥可能降低維生素 B12 的吸收。",
    ],
)
def test_一般用語與病名裡的數字不擋(text):
    assert not contains_quantity(text)
