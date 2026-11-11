"""Deterministic datetime and IANA timezone validation."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
