"""藥名表：夾具涵蓋 16 個用藥類別；完整匯出檔存在時，每個有效成分都對得到品名。"""

import pytest

from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.drug_names import (
    DATA_DIR,
    FULL_TABLE,
    check_drug_names,
    load_sample_drug_names,
    read_drug_names,
)


def test_sample_table_is_consistent_and_covers_every_drug_class():
    table = load_sample_drug_names()
    ref = load_reference_data()

    assert check_drug_names(table, ref.drugs) == []
    covered = {ref.drugs.class_of(code) for e in table.entries for code in e.ingredients}
    assert covered == {c.code for c in ref.drugs.classes}


@pytest.mark.skipif(not (DATA_DIR / FULL_TABLE).exists(), reason="沒有完整匯出檔")
def test_full_table_maps_every_catalog_ingredient_to_some_product_name():
    table = read_drug_names(DATA_DIR / FULL_TABLE)
    ref = load_reference_data()

    assert check_drug_names(table, ref.drugs) == []
    covered = {code for e in table.entries for code in e.ingredients}
    missing = {i.code for i in ref.drugs.ingredients} - covered
    assert missing == set()
