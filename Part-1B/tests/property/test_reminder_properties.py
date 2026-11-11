from datetime import date, datetime

from hypothesis import given, strategies as st

from reminder_agent.contracts.models import Recurrence
from reminder_agent.domain.recurrence import iter_occurrences
from reminder_agent.domain.time import validate_zoned_datetime


@given(
    year=st.integers(min_value=2001, max_value=2098),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),
)
def test_valid_calendar_dates_roundtrip_to_iana_timezone(year, month, day):
    local = datetime(year, month, day, 9, 30)
    aware = local.replace(tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York"))
    result = validate_zoned_datetime(aware, "America/New_York")
    assert result.replace(tzinfo=None) == local


@given(count=st.integers(min_value=1, max_value=20))
def test_occurrence_count_is_a_total_including_the_first(count):
    recurrence = Recurrence.model_validate({
        "frequency":"daily",
        "interval":1,
        "weekdays":None,
        "day_of_month":None,
        "month":None,
        "day":None,
        "timezone":"UTC",
        "end_condition":{"until":None,"occurrences":count},
    })
    dates = iter_occurrences(recurrence, date(2026, 1, 1), date(2026, 3, 1))
    assert len(dates) == count
