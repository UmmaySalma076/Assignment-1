from datetime import date

import pytest
from pydantic import ValidationError

from reminder_agent.contracts.models import Recurrence
from reminder_agent.domain.recurrence import iter_occurrences, validate_recurrence


def recurrence(**overrides):
    values = {
        "frequency": "monthly",
        "interval": 1,
        "weekdays": None,
        "day_of_month": 31,
        "month": None,
        "day": None,
        "timezone": "America/New_York",
        "end_condition": {"until": "2026-12-31", "occurrences": None},
    }
    values.update(overrides)
    return Recurrence.model_validate(values)


def test_recurrence_requires_exactly_one_end_selector():
    with pytest.raises(ValidationError):
        recurrence(end_condition={"until": None, "occurrences": None})
    with pytest.raises(ValidationError):
        recurrence(end_condition={"until": "2026-12-31", "occurrences": 4})
    with pytest.raises(ValidationError):
        recurrence(end_condition={"until": None, "occurrences": 0})


def test_frequency_selectors_are_conditional():
    with pytest.raises(ValidationError):
        recurrence(frequency="weekly")
    weekly = recurrence(
        frequency="weekly",
        weekdays=["MO", "WE"],
        day_of_month=None,
    )
    assert weekly.frequency == "weekly"


def test_monthly_31_skips_months_without_day_and_includes_until():
    value = recurrence(end_condition={"until": "2026-03-31", "occurrences": None})
    assert iter_occurrences(value, date(2026, 1, 31), date(2026, 5, 1)) == [
        date(2026, 1, 31),
        date(2026, 3, 31),
    ]


def test_yearly_february_29_occurs_only_on_leap_day():
    value = recurrence(
        frequency="yearly",
        day_of_month=None,
        month=2,
        day=29,
        end_condition={"until": "2030-12-31", "occurrences": None},
    )
    dates = iter_occurrences(value, date(2024, 1, 1), date(2030, 1, 1))
    assert dates == [date(2024, 2, 29), date(2028, 2, 29)]


def test_until_cannot_precede_first_occurrence():
    value = recurrence(end_condition={"until": "2026-03-01", "occurrences": None})
    with pytest.raises(ValueError, match="precedes"):
        validate_recurrence(value, date(2026, 3, 2))
