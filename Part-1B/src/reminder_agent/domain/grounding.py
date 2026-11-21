"""Derive supported reminder slots from request text and trusted context."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from reminder_agent.contracts.models import (
    InterpretRequest,
    Recurrence,
    RecurrenceEnd,
    ReminderAction,
    ReminderReference,
)
from reminder_agent.domain.recurrence import WEEKDAYS, validate_recurrence
from reminder_agent.domain.safety import refusal_for_request
from reminder_agent.domain.time import require_unambiguous_local_time, resolve_relative_time

_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_CLOCK = r"(?:[0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?|noon|midnight)"
_ZONE = re.compile(
    r"(?<!\w)(?:[A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+)+|(?i:UTC|GMT))(?!\w)"
)
_CREATE = re.compile(
    r"(?:^|[.!?]\s+)(?:please\s+)?(?:remind me to|(?:set|create) (?:up )?a reminder to)\s+",
    re.IGNORECASE,
)
_OUTPUT_OVERRIDE = re.compile(
    r"(?:please\s+)?(?:ignore|disregard|override)\s+(?:(?:all|the)\s+)*"
    r"(?:(?:earlier|previous|prior|above|system|developer)\s+)?(?:instructions?|rules?|prompts?)"
    r"(?:\s+and\s+(?:return|respond|print|output|claim|say|write|tell me)\b[^.!?]*)?",
    re.IGNORECASE,
)
_CHANGE = re.compile(
    r"(?:please\s+)?(?P<verb>reschedule|move|snooze|postpone|delay)\s+(?P<body>.+)",
    re.IGNORECASE,
)
_CHANGE_BOUNDARY = re.compile(r"\s+(?=(?:to|until|for|on|in)\s+)", re.IGNORECASE)
_ACTION_SEPARATOR = re.compile(
    r"\s+and (?:then )?(?:to|remind me to)\s+|;\s*", re.IGNORECASE
)
_SCHEDULE_START = re.compile(
    rf"\s+(?=(?:(?:on\s+)?{_DATE}|in\s+[A-Za-z0-9]+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)"
    r"|(?:today|tomorrow)\s+at|every\s+|(?:daily|weekly|monthly|yearly|annually)\b))",
    re.IGNORECASE,
)
_ELAPSED = re.compile(r"(?:for|in)\s+([A-Za-z0-9]+)\s+(minute|hour|day)s?", re.IGNORECASE)
_BARE_HOUR = re.compile(r"\bat\s+(?:[1-9]|1[0-2])$", re.IGNORECASE)
_CLOCK_TAIL = re.compile(rf"(?:\bat|\b{_DATE}|\btoday|\btomorrow)\s+{_CLOCK}$", re.IGNORECASE)
_DATE_TAIL = re.compile(r"\b(?:today|tomorrow)$", re.IGNORECASE)
_END = re.compile(
    rf"\s+(?:(?:until\s+(?P<until>{_DATE}))|for\s+(?P<count>[1-9][0-9]*)\s+occurrences?"
    r"|(?P<indefinite>indefinitely|forever|no end date|without end))$",
    re.IGNORECASE,
)
_WEEKDAYS = dict(zip(
    "monday tuesday wednesday thursday friday saturday sunday".split(), WEEKDAYS, strict=True,
))
_MONTHS = {
    name: number
    for number, name in enumerate(
        "january february march april may june july august september october november december".split(),
        start=1,
    )
}


def ground_actions(
    request: InterpretRequest, clock: datetime, timezone_name: str | None = None
) -> list[ReminderAction] | None:
    """Ground complete, unambiguous action slots for supported phrasing."""
    if clock.utcoffset() is None or refusal_for_request(request.text):
        return None

    text = request.text.rstrip(".!? \t\n")
    selected_timezone = timezone_name or request.timezone
    try:
        change = _CHANGE.fullmatch(text)
        if change:
            return [_ground_change(change, request.reminder_context, clock, selected_timezone)]

        clauses = _create_clauses(text)
        if clauses is None:
            return None
        return [_ground_create(clause, clock, selected_timezone) for clause in clauses]
    except (ValueError, OverflowError, ZoneInfoNotFoundError):
        return None


def explicit_target_unresolved(request: InterpretRequest) -> bool:
    """Check whether an explicit change names one verified reminder target."""
    command = _CHANGE.fullmatch(request.text.rstrip(".!? \t\n"))
    if command is None:
        return False
    return len(_change_targets(command["body"], request.reminder_context)) != 1


def explicit_target(request: InterpretRequest) -> ReminderReference | None:
    """Return the uniquely matched trusted target of an explicit reminder change."""
    command = _CHANGE.fullmatch(request.text.rstrip(".!? \t\n"))
    if command is None:
        return None
    targets = _change_targets(command["body"], request.reminder_context)
    return targets[0][0] if len(targets) == 1 else None


def grounding_unresolved_fields(request: InterpretRequest) -> set[str]:
    """Find independent gaps in separately scheduled actions and bare hours."""
    text = request.text.rstrip(".!? \t\n")
    change = _CHANGE.fullmatch(text)
    if change is not None:
        targets = _change_targets(change["body"], request.reminder_context)
        if len(targets) == 1 and _BARE_HOUR.search(_clock_tail(targets[0][1])):
            return {"time"}
        return set()

    clauses = _create_clauses(text)
    if clauses is None:
        return set()
    fields = set()
    for clause in clauses:
        boundary = _SCHEDULE_START.search(clause)
        schedule = _clock_tail(clause[boundary.end():] if boundary else clause)
        bare_hour = _BARE_HOUR.search(schedule)
        if bare_hour:
            fields.add("time")
        if len(clauses) == 1:
            continue
        if boundary is None and not _DATE_TAIL.search(schedule):
            fields.add("date")
        elapsed = _ELAPSED.fullmatch(schedule)
        if not _CLOCK_TAIL.search(schedule) and not (elapsed and elapsed[2].lower() != "day"):
            fields.add("time")
    return fields


def _create_clauses(text: str) -> list[str] | None:
    commands = list(_CREATE.finditer(text))
    if len(commands) != 1:
        return None
    command = commands[0]
    prefix = text[:command.start()].strip()
    if prefix and not _OUTPUT_OVERRIDE.fullmatch(prefix):
        return None
    body = text[command.end():]
    clauses = []
    start = 0
    for separator in _ACTION_SEPARATOR.finditer(body):
        clause = body[start:separator.start()]
        if (
            separator[0].startswith(";")
            or "remind me to" in separator[0].lower()
            or _SCHEDULE_START.search(clause)
            or _CLOCK_TAIL.search(_clock_tail(clause))
        ):
            clauses.append(clause)
            start = separator.end()
    clauses.append(body[start:])
    return clauses


def _clock_tail(schedule: str) -> str:
    schedule = " ".join(_ZONE.sub("", schedule).split())
    end = _END.search(schedule)
    return schedule[:end.start()] if end else schedule


def _ground_create(clause: str, clock: datetime, timezone_name: str | None) -> ReminderAction:
    boundary = _SCHEDULE_START.search(clause)
    if boundary is None:
        raise ValueError("Unsupported reminder schedule")
    subject = clause[:boundary.start()].strip()
    schedule, zone = _zone(clause[boundary.end():], timezone_name)
    recurrence = None
    if re.match(r"^(?:every|daily|weekly|monthly|yearly|annually)\b", schedule, re.I):
        due_at, recurrence = _recurring_due(schedule, clock, zone)
    else:
        due_at = _single_due(schedule, clock, zone)
    return ReminderAction(
        intent="create", subject=subject, due_at=due_at, timezone=zone.key,
        recurrence=recurrence, target_reference=None,
    )


def _change_targets(
    body: str, context: list[ReminderReference]
) -> list[tuple[ReminderReference, str]]:
    boundaries = [(match.start(), match.end()) for match in _CHANGE_BOUNDARY.finditer(body)]
    boundaries.append((len(body), len(body)))
    matches = []
    for start, end in boundaries:
        stated = body[:start].strip().casefold()
        bare = re.sub(r"^(?:my|the)\s+", "", stated)
        for item in context:
            names = {item.subject.casefold(), item.reference.casefold()}
            if stated in names or bare in names:
                matches.append((item, body[end:]))
    return matches


def _ground_change(
    command: re.Match[str],
    context: list[ReminderReference],
    clock: datetime,
    timezone_name: str | None,
) -> ReminderAction:
    targets = _change_targets(command["body"], context)
    if len(targets) != 1:
        raise ValueError("Reminder target must match one trusted reference")
    target, requested_schedule = targets[0]

    schedule, zone = _zone(requested_schedule, timezone_name)
    snooze = command["verb"].casefold() in {"snooze", "postpone", "delay"}
    duration = _ELAPSED.fullmatch(schedule) if snooze else None
    if duration:
        base = (target.due_at or clock).astimezone(timezone.utc)
        resolved = resolve_relative_time(
            f"in {duration[1]} {duration[2]}", base, "UTC"
        )
        if resolved is None:
            raise ValueError("Unsupported snooze duration")
        if not isinstance(resolved, datetime):
            resolved = datetime.combine(resolved, base.timetz())
        due_at = resolved.astimezone(zone)
    else:
        due_at = _single_due(re.sub(r"^(?:to|until)\s+", "", schedule, flags=re.I), clock, zone)

    recurrence = None if snooze else target.recurrence
    if recurrence is not None:
        if recurrence.timezone != zone.key:
            raise ValueError("Reschedule must preserve the recurrence timezone")
        validate_recurrence(recurrence, due_at.date())
    return ReminderAction(
        intent="snooze" if snooze else "reschedule", subject=target.subject,
        due_at=due_at, timezone=zone.key, recurrence=recurrence,
        target_reference=target.reference,
    )


def _zone(schedule: str, preferred: str | None) -> tuple[str, ZoneInfo]:
    zones = {"UTC" if name.upper() in {"GMT", "UTC"} else name for name in _ZONE.findall(schedule)}
    equivalent_preferred = "UTC" if preferred and preferred.upper() in {"GMT", "UTC"} else preferred
    if len(zones) > 1 or (zones and equivalent_preferred and equivalent_preferred not in zones):
        raise ValueError("Conflicting timezones")
    name = preferred or next(iter(zones), None)
    if name is None:
        raise ValueError("A timezone is required")
    return " ".join(_ZONE.sub("", schedule).split()), ZoneInfo(name)


def _wall_clock(text: str) -> time:
    lowered = text.strip().lower()
    if lowered in {"noon", "midnight"}:
        return time(12 if lowered == "noon" else 0)
    match = re.fullmatch(r"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)?", lowered)
    if match is None:
        raise ValueError("Unsupported clock")
    hours, minutes, meridiem = match.groups()
    hour = int(hours)
    if meridiem:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid 12-hour clock")
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    elif minutes is None and not (hours.startswith("0") or hour >= 13):
        raise ValueError("Use a 24-hour time or specify AM or PM")
    return time(hour, int(minutes or 0))


def _single_due(schedule: str, clock: datetime, zone: ZoneInfo) -> datetime:
    explicit = re.fullmatch(rf"(?:on\s+)?({_DATE})\s+(?:at\s+)?({_CLOCK})", schedule, re.I)
    if explicit:
        wall = datetime.combine(date.fromisoformat(explicit[1]), _wall_clock(explicit[2]))
        return require_unambiguous_local_time(wall, zone.key)
    date_part, _, time_part = schedule.lower().partition(" at ")
    if date_part in {"today", "tomorrow"}:
        resolved = clock.astimezone(zone).date() + timedelta(days=date_part == "tomorrow")
    elif re.fullmatch(
        r"in\s+[A-Za-z0-9]+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)", date_part
    ):
        resolved = resolve_relative_time(date_part, clock, zone.key)
    else:
        raise ValueError("Unsupported relative schedule")
    if isinstance(resolved, datetime) and not time_part:
        return resolved.astimezone(zone)
    if resolved is not None and not isinstance(resolved, datetime) and time_part:
        wall = datetime.combine(resolved, _wall_clock(time_part))
        return require_unambiguous_local_time(wall, zone.key)
    raise ValueError("Incomplete or conflicting relative schedule")


def _recurring_due(schedule: str, clock: datetime, zone: ZoneInfo) -> tuple[datetime, Recurrence]:
    end = _END.search(schedule)
    if end is None:
        raise ValueError("Recurring reminders require an explicit end")
    end_condition = None
    if end["until"]:
        end_condition = RecurrenceEnd(until=date.fromisoformat(end["until"]))
    elif end["count"]:
        end_condition = RecurrenceEnd(occurrences=int(end["count"]))

    parts = re.fullmatch(
        rf"(.+?)(?:\s+starting(?:\s+on)?\s+({_DATE}))?\s+at\s+({_CLOCK})",
        schedule[:end.start()], re.IGNORECASE,
    )
    if parts is None:
        raise ValueError("Recurring reminders require an explicit clock time")
    rule, start_date, time_text = parts.groups()
    recurrence = Recurrence(
        **_recurrence_rule(rule.lower()), timezone=zone.key, end_condition=end_condition
    )
    wall = _wall_clock(time_text)
    if start_date:
        due_at = require_unambiguous_local_time(
            datetime.combine(date.fromisoformat(start_date), wall), zone.key
        )
    else:
        due_at = _next_occurrence(recurrence, clock, wall)
    validate_recurrence(recurrence, due_at.date())
    return due_at, recurrence


def _recurrence_rule(rule: str) -> dict[str, Any]:
    interval = 1
    explicit_interval = re.match(r"^every ([1-9][0-9]*) ", rule)
    if explicit_interval:
        interval = int(explicit_interval[1])
        rule = "every " + rule[explicit_interval.end():]
    fields = {"interval": interval, "weekdays": None, "day_of_month": None, "month": None, "day": None}
    if rule in {"daily", "every day", "every days"}:
        return dict(fields, frequency="daily")
    monthly = re.fullmatch(
        r"(?:monthly|every months?) on (?:the |day )?([0-9]{1,2})(?:st|nd|rd|th)?", rule
    )
    if monthly:
        return dict(fields, frequency="monthly", day_of_month=int(monthly[1]))
    yearly = re.fullmatch(
        r"(?:yearly|annually|every years?) on ([a-z]+) ([0-9]{1,2})(?:st|nd|rd|th)?", rule
    )
    if yearly and yearly[1] in _MONTHS:
        return dict(fields, frequency="yearly", month=_MONTHS[yearly[1]], day=int(yearly[2]))

    weekdays_text = re.sub(r"^(?:(?:weekly|every weeks?) on|every)\s+", "", rule)
    weekdays = [part.strip() for part in re.split(r",|\band\b", weekdays_text) if part.strip()]
    if weekdays_text != rule and weekdays and all(day in _WEEKDAYS for day in weekdays):
        return dict(fields, frequency="weekly", weekdays=[_WEEKDAYS[day] for day in weekdays])
    raise ValueError("Unsupported recurring schedule")


def _next_occurrence(recurrence: Recurrence, clock: datetime, wall: time) -> datetime:
    zone = ZoneInfo(recurrence.timezone)
    local_now = clock.astimezone(zone)
    for offset in range(8 * 366 + 1):
        day = local_now.date() + timedelta(days=offset)
        if recurrence.weekdays is not None and WEEKDAYS[day.weekday()] not in recurrence.weekdays:
            continue
        if recurrence.frequency == "monthly" and day.day != recurrence.day_of_month:
            continue
        if recurrence.frequency == "yearly" and (day.month, day.day) != (recurrence.month, recurrence.day):
            continue
        first_wall = datetime.combine(day, wall)
        if first_wall >= local_now.replace(tzinfo=None):
            return require_unambiguous_local_time(first_wall, zone.key)
    raise ValueError("No unambiguous first recurrence")
