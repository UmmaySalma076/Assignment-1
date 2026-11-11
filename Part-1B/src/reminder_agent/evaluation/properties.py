"""Repeatable generated temporal and recurrence boundary properties."""

from __future__ import annotations

from datetime import date, datetime
from itertools import product

from pydantic import ValidationError

from reminder_agent.contracts.models import Recurrence
from reminder_agent.domain.recurrence import iter_occurrences
from reminder_agent.domain.time import (
    local_time_candidates,
    validate_zoned_datetime,
)


def run_property_checks() -> dict[str, object]:
    checked_dates = 0
    for year, month, day in product(range(2024, 2029), range(1, 13), (1, 15, 28)):
        try:
            wall = datetime(year, month, day, 9, 15)
        except ValueError:
            continue
        zone = __import__("zoneinfo").ZoneInfo("America/New_York")
        local = wall.replace(tzinfo=zone)
        validate_zoned_datetime(local, "America/New_York")
        checked_dates += 1

    dst_gap = local_time_candidates(datetime(2026, 3, 8, 2, 30), "America/New_York")
    dst_fold = local_time_candidates(datetime(2026, 11, 1, 1, 30), "America/New_York")

    monthly = Recurrence.model_validate({
        "frequency": "monthly",
        "interval": 1,
        "weekdays": None,
        "day_of_month": 31,
        "month": None,
        "day": None,
        "timezone": "UTC",
        "end_condition": {"until": "2026-04-30", "occurrences": None},
    })
    monthly_dates = iter_occurrences(monthly, date(2026, 1, 31), date(2026, 4, 30))

    leap_yearly = Recurrence.model_validate({
        "frequency": "yearly",
        "interval": 1,
        "weekdays": None,
        "day_of_month": None,
        "month": 2,
        "day": 29,
        "timezone": "UTC",
        "end_condition": {"until": "2028-12-31", "occurrences": None},
    })
    leap_dates = iter_occurrences(leap_yearly, date(2024, 1, 1), date(2028, 12, 31))
    try:
        Recurrence.model_validate({
            "frequency": "weekly",
            "interval": 1,
            "weekdays": [],
            "day_of_month": None,
            "month": None,
            "day": None,
            "timezone": "UTC",
            "end_condition": {"until": "2026-12-31", "occurrences": None},
        })
        weekly_nonempty = False
    except ValidationError:
        weekly_nonempty = True

    checks = {
        "valid_zone_roundtrips": checked_dates == 180,
        "dst_gap_rejected": len(dst_gap) == 0,
        "dst_fold_ambiguous": len(dst_fold) == 2,
        "monthly_unavailable_dates_skipped": monthly_dates
        == [date(2026, 1, 31), date(2026, 3, 31)],
        "leap_day_occurs_only_in_leap_year": leap_dates
        == [date(2024, 2, 29), date(2028, 2, 29)],
        "weekly_selector_required": weekly_nonempty,
    }
    return {"passed": all(checks.values()), "checks": checks, "generated_dates": checked_dates}
