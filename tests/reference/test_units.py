import pytest

from nutrition_agent.reference import IngredientCategory, UnitNotConvertible, load_reference_data


@pytest.fixture(scope="module")
def units():
    return load_reference_data().units


def test_維生素D的1微克等於40IU(units):
    assert units.convert("vitamin_d", 2000, "IU", "ug") == pytest.approx(50)


def test_維生素E的IU換算成α_TE每IU約0點67毫克(units):
    assert units.convert("vitamin_e", 100, "IU", "mg_alpha_te") == pytest.approx(67)


def test_維生素E的dl_α生育醇醋酸酯每毫克0點67α_TE(units):
    assert units.convert(
        "vitamin_e", 100, "mg_dl_alpha_tocopheryl_acetate", "mg_alpha_te"
    ) == pytest.approx(67)


def test_菸鹼素的毫克等於NE毫克(units):
    assert units.convert("niacin", 20, "mg", "mg_ne") == pytest.approx(20)


def test_葉酸合成葉酸微克乘1點7換算DFE(units):
    assert units.convert("folate", 400, "ug", "ug_dfe") == pytest.approx(680)


def test_通用質量單位可互換(units):
    assert units.convert("calcium", 0.5, "g", "mg") == pytest.approx(500)
    assert units.convert("selenium", 0.05, "mg", "ug") == pytest.approx(50)


def test_同單位不需換算(units):
    assert units.convert("zinc", 12, "mg", "mg") == 12


def test_沒有換算途徑時明確失敗而不是猜(units):
    with pytest.raises(UnitNotConvertible):
        units.convert("calcium", 10, "IU", "mg")


def test_換算只涉及目標營養素():
    data = load_reference_data()
    targets = {i.code for i in data.ingredients.by_category(IngredientCategory.TARGET_NUTRIENT)}
    assert {r.nutrient_code for r in data.units.rules if r.nutrient_code} <= targets
