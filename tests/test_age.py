from datetime import date

import pytest

from nutrition_agent.accounts import UnderageError, age_on, require_adult


def test_age_counts_full_years_once_birth_month_is_reached():
    assert age_on(1950, 6, date(2026, 6, 1)) == 76
    assert age_on(1950, 6, date(2026, 5, 31)) == 75


def test_require_adult_accepts_exactly_19():
    assert require_adult(2007, 3, date(2026, 3, 1)) == 19


def test_require_adult_explains_underage():
    with pytest.raises(UnderageError) as err:
        require_adult(2007, 4, date(2026, 3, 31))

    assert "未滿 19 歲" in str(err.value)
