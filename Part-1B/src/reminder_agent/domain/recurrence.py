"""Calendar rules for supported recurrence schedules."""

from __future__ import annotations

from datetime import date, timedelta

from reminder_agent.contracts.models import Recurrence

WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def validate_recurrence(
    recurrence: Recurrence, first_occurrence: date | None = None
) -> None:
    end = recurrence.end_condition
    if end and end.until and first_occurrence and end.until < first_occurrence:
        raise ValueError("recurrence until date precedes first occurrence")
    if first_occurrence is None:
        return
    if recurrence.frequency == "weekly" and WEEKDAYS[first_occurrence.weekday()] not in (recurrence.weekdays or []):
        raise ValueError("first occurrence does not match weekly weekdays")
    if recurrence.frequency == "monthly" and first_occurrence.day != recurrence.day_of_month:
        raise ValueError("first occurrence does not match monthly day")
    if recurrence.frequency == "yearly" and (
        first_occurrence.month != recurrence.month or first_occurrence.day != recurrence.day
    ):
        raise ValueError("first occurrence does not match yearly date")


def occurs_on(
    recurrence: Recurrence, day: date, anchor: date = date(2000, 1, 3)
) -> bool:
    """Return whether a calendar date is selected, including interval anchors."""
    if recurrence.frequency == "daily":
        days = (day - anchor).days
        return days >= 0 and days % recurrence.interval == 0
    if recurrence.frequency == "weekly":
        weeks = (day - anchor).days // 7
        return weeks >= 0 and weeks % recurrence.interval == 0 and WEEKDAYS[day.weekday()] in (recurrence.weekdays or [])
    if recurrence.frequency == "monthly":
        months = (day.year - 2000) * 12 + day.month - 1
        return months >= 0 and months % recurrence.interval == 0 and day.day == recurrence.day_of_month
    years = day.year - 2000
    return years >= 0 and years % recurrence.interval == 0 and day.month == recurrence.month and day.day == recurrence.day


def iter_occurrences(
    recurrence: Recurrence, start: date, stop: date
) -> list[date]:
    """Enumerate selected dates, naturally skipping invalid monthly days."""
    end_condition = recurrence.end_condition
    if end_condition and end_condition.until:
        stop = min(stop, end_condition.until)
    if stop < start:
        return []
    selected: list[date] = []
    current = start
    while current <= stop:
        if occurs_on(recurrence, current, start):
            selected.append(current)
            end = recurrence.end_condition
            if end and end.occurrences is not None and len(selected) >= end.occurrences:
                break
        current += timedelta(days=1)
    return selected
