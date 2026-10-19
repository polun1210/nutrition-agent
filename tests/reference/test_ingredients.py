from nutrition_agent.reference import IngredientCategory, load_reference_data


def test_目標營養素共13項且依固定順序排列():
    data = load_reference_data()
    targets = data.ingredients.by_category(IngredientCategory.TARGET_NUTRIENT)
    assert len(targets) == 13
    assert [i.code for i in targets][:3] == ["calcium", "magnesium", "iron"]
    assert [i.sort_order for i in targets] == sorted(i.sort_order for i in targets)


def test_允許成分共3項():
    data = load_reference_data()
    allowed = data.ingredients.by_category(IngredientCategory.ALLOWED_INGREDIENT)
    assert {i.code for i in allowed} == {"red_yeast_rice", "glucosamine", "omega_3"}


def test_同義詞可反查標準代碼且含範圍外成分():
    data = load_reference_data()
    assert data.ingredients.find("維他命D").code == "vitamin_d"
    assert data.ingredients.find("Q10").category is IngredientCategory.OUT_OF_SCOPE
    assert data.ingredients.find("不存在的成分") is None


def test_資料帶版本號():
    data = load_reference_data()
    assert data.versions["ingredients"]
    assert data.version
