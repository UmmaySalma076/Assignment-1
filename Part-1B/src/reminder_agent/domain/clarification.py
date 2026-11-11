"""Deterministic justification checks for clarification proposals."""

from __future__ import annotations

import re
from datetime import date, datetime

from reminder_agent.contracts.models import InterpretRequest

NUMBER_WORDS = r"(?:one|two|three|four|five|six|seven|eight|nine|ten)"
DATE_RE = re.compile(
    rf"\b(?:today|tomorrow|tonight|next\s+\w+|in\s+(?:\d+|{NUMBER_WORDS})\s+(?:days?|weeks?|months?|years?)|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    rf"(?:\b(?:at\s+|T)\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?\b|"
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b(?:noon|midnight)\b|"
    rf"\b(?:in|for)\s+(?:\d+|{NUMBER_WORDS})\s+(?:minutes?|hours?|days?)\b)",
    re.IGNORECASE,
)
RECURRENCE_RE = re.compile(r"\b(daily|every|weekly|monthly|yearly|annually|weekdays?)\b", re.I)
CHANGE_RE = re.compile(r"\b(reschedule|move|snooze|postpone|delay)\b", re.I)
CONFLICT_RE = re.compile(r"\b(?:but|instead|actually|not\s+\w+)\b", re.I)


def justified_fields(request: InterpretRequest) -> set[str]:
    text = request.text
    fields: set[str] = set()
    recurrence_requested = bool(RECURRENCE_RE.search(text))
    relative_duration = bool(
        re.search(
            rf"\b(?:in|for)\s+(?:\d+|{NUMBER_WORDS})\s+(?:minutes?|hours?|days?)\b",
            text,
            re.I,
        )
    )
    if not DATE_RE.search(text) and not recurrence_requested and not relative_duration:
        fields.add("date")
    if re.search(r"\bnext\s+(?:mon|tue|wed|thu|fri|sat|sun)\w*\b", text, re.I):
        fields.add("date")
    for candidate in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text):
        try:
            date.fromisoformat(candidate)
        except ValueError:
            fields.add("date")
    if not TIME_RE.search(text):
        fields.add("time")
    if request.timezone is None and not mentions_timezone(text):
        fields.add("timezone")
    elif request.timezone is not None and _timezone_context_conflicts(text, request.timezone):
        fields.add("timezone")
    recurrence_requested = bool(RECURRENCE_RE.search(text))
    if recurrence_requested and re.search(r"\b(?:weekly|every\s+week)\b", text, re.I):
        if not re.search(
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekdays?)\b",
            text,
            re.I,
        ):
            fields.add("recurrence")
    if recurrence_requested and re.search(r"\b(?:monthly|every\s+month)\b", text, re.I):
        if not re.search(r"\b(?:day\s+\d{1,2}|on\s+the\s+\d{1,2}(?:st|nd|rd|th)?)\b", text, re.I):
            fields.add("recurrence")
    if recurrence_requested and re.search(
        r"\b(?:yearly|annually|every\s+year)\b", text, re.I
    ):
        if not re.search(
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
            text,
            re.I,
        ):
            fields.add("recurrence")
    if recurrence_requested and not re.search(
        r"\b(?:until\s+\d{4}-\d{2}-\d{2}|for\s+\d+\s+occurrences?|indefinitely|indefinite|forever|no end date|without end)\b",
        text,
        re.I,
    ):
        fields.add("recurrence")
    if CHANGE_RE.search(text) and (
        not request.reminder_context
        or (
            len(request.reminder_context) > 1
            and len(
                [
                    item
                    for item in request.reminder_context
                    if item.subject.casefold() in text.casefold()
                    or item.reference.casefold() in text.casefold()
                ]
            )
            != 1
        )
    ):
        fields.add("target")
    if CONFLICT_RE.search(text) and len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)) > 1:
        fields.add("conflict")
    if request.timezone:
        from reminder_agent.domain.time import local_time_candidates

        explicit_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        explicit_times = re.findall(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b", text, re.I)
        for date_text in explicit_dates:
            for hour_text, minute_text, meridiem in explicit_times:
                try:
                    day = date.fromisoformat(date_text)
                    hour = int(hour_text)
                    if meridiem:
                        hour = hour % 12 + (12 if meridiem.upper() == "PM" else 0)
                    candidates = local_time_candidates(
                        datetime.combine(day, datetime.min.time()).replace(
                            hour=hour, minute=int(minute_text)
                        ),
                        request.timezone,
                    )
                except (ValueError, OverflowError):
                    continue
                if len(candidates) != 1:
                    fields.add("time")
    return fields


def validate_clarification(request: InterpretRequest, unresolved_fields: list[str]) -> None:
    justified = justified_fields(request)
    if not justified:
        raise ValueError("clarification is not justified by request or context")
    if any(not any(_field_matches(candidate, known) for known in justified) for candidate in unresolved_fields):
        raise ValueError("clarification cites an unresolved field not supported by the request")


def _field_matches(candidate: str, known: str) -> bool:
    value = candidate.casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "date": {"date", "day"},
        "time": {"time", "hour"},
        "timezone": {"timezone", "time_zone", "zone"},
        "target": {"target", "reminder", "reminder_reference"},
        "recurrence": {"recurrence", "schedule", "frequency"},
        "conflict": {"conflict", "date", "time"},
    }
    return value in aliases.get(known, {known})


def mentions_timezone(text: str) -> bool:
    return bool(
        re.search(r"\b(?:UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT)\b", text, re.I)
        or re.search(r"\b(?:[A-Za-z_+-]+/)+[A-Za-z_+-]+\b", text)
        or re.search(r"\b(?:New York|London|Los Angeles|Tokyo|Paris)\b", text, re.I)
    )


def _timezone_context_conflicts(text: str, timezone_name: str) -> bool:
    zones = re.findall(r"\b(?:[A-Za-z_+-]+/)+[A-Za-z_+-]+\b", text)
    if zones and any(zone != timezone_name for zone in zones):
        return True
    named_zones = {
        "new york": "America/New_York",
        "london": "Europe/London",
        "los angeles": "America/Los_Angeles",
        "tokyo": "Asia/Tokyo",
        "paris": "Europe/Paris",
    }
    return any(
        label in text.casefold() and timezone_name != zone
        for label, zone in named_zones.items()
    )
