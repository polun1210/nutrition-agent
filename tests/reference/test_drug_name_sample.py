"""藥名表夾具：成分都在目錄內，且 16 個用藥類別都有至少一筆。"""

from nutrition_agent.reference import load_reference_data
from nutrition_agent.reference.drug_names import check_drug_names, load_drug_names


def test_sample_table_is_consistent_and_covers_every_drug_class():
    table = load_drug_names()
    ref = load_reference_data()

    assert check_drug_names(table, ref.drugs) == []
    covered = {ref.drugs.class_of(code) for e in table.entries for code in e.ingredients}
    assert covered == {c.code for c in ref.drugs.classes}
