"""Deterministic datetime and IANA timezone validation."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_SMALL_NUMBERS = (
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
)
_RELATIVE_COUNT = re.compile(
    rf"\bin\s+([0-9]+|{'|'.join(_SMALL_NUMBERS)})\s+"
    r"(minute|hour|day|week|month|year)s?\b"
)


class TemporalValidationError(ValueError):
    """Raised when a proposed reminder time is invalid or ambiguous."""


def validate_zoned_datetime(value: datetime, timezone_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TemporalValidationError("due_at must include a UTC offset")
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TemporalValidationError("unknown IANA timezone") from exc
    local = value.astimezone(zone)
    if local.utcoffset() != value.utcoffset():
        raise TemporalValidationError("UTC offset does not match timezone")
    return local


def resolve_relative_time(
    text: str, reference_time: datetime, timezone_name: str
) -> date | datetime | None:
    """Resolve one explicit duration to an elapsed instant or a local calendar date."""
    matches = _RELATIVE_COUNT.findall(text.casefold())
    if len(matches) != 1 or re.search(r"\b\d{4}-\d{2}-\d{2}\b", text):
        return None
    count, unit = matches[0]
    amount = int(count) if count.isdigit() else _SMALL_NUMBERS.index(count) + 1
    try:
        if unit in {"minute", "hour"}:
            minutes = amount * 60 if unit == "hour" else amount
            return reference_time.astimezone(timezone.utc) + timedelta(minutes=minutes)
        local_date = reference_time.astimezone(ZoneInfo(timezone_name)).date()
        if unit in {"day", "week"}:
            days = amount * 7 if unit == "week" else amount
            return local_date + timedelta(days=days)
        months = amount * 12 if unit == "year" else amount
        year, month_index = divmod(local_date.year * 12 + local_date.month - 1 + months, 12)
        return local_date.replace(year=year, month=month_index + 1)
    except (OverflowError, ValueError) as exc:
        raise TemporalValidationError(
            "relative schedule does not resolve to a valid date and time"
        ) from exc


def local_time_candidates(local: datetime, timezone_name: str) -> list[datetime]:
    if local.tzinfo is not None:
        raise TemporalValidationError("local wall time must be naive")
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TemporalValidationError("unknown IANA timezone") from exc
    candidates: dict[datetime, datetime] = {}
    for fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(timezone.utc).astimezone(zone)
        if round_trip.replace(tzinfo=None) == local:
            candidates[candidate.astimezone(timezone.utc)] = candidate
    return list(candidates.values())


def require_unambiguous_local_time(local: datetime, timezone_name: str) -> datetime:
    candidates = local_time_candidates(local, timezone_name)
    if not candidates:
        raise TemporalValidationError("local time does not exist in timezone")
    if len(candidates) > 1:
        raise TemporalValidationError("local time is ambiguous in timezone")
    return candidates[0]
