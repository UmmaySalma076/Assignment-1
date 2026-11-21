"""Use-case orchestration and fail-closed validation of model proposals."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from reminder_agent.api.errors import ServiceException
from reminder_agent.contracts.models import (
    OUTCOME_ADAPTER,
    ClarificationResponse,
    InterpretRequest,
    ModelOutcome,
    Recurrence,
    RefusalResponse,
    ReminderResponse,
)
from reminder_agent.domain.clarification import (
    justified_fields,
    mentions_timezone,
    validate_clarification,
)
from reminder_agent.domain.grounding import (
    explicit_target,
    explicit_target_unresolved,
    ground_actions,
    grounding_unresolved_fields,
)
from reminder_agent.domain.recurrence import validate_recurrence
from reminder_agent.domain.safety import refusal_for_request
from reminder_agent.domain.targets import resolve_target
from reminder_agent.domain.time import (
    TemporalValidationError,
    local_time_candidates,
    resolve_relative_time,
    validate_zoned_datetime,
)
from reminder_agent.services.ollama import ModelReply


class ModelClient(Protocol):
    async def generate(self, prompt: str) -> ModelReply: ...


StructuredGenerator = Callable[[str, dict[str, Any]], Awaitable[ModelReply]]

_CLARIFICATION_QUESTIONS = {
    "date": ("Which date should I use?", "What day should the reminder use?"),
    "time": ("Which exact local time or UTC offset should I use?", "What time or offset did you intend?"),
    "timezone": ("Which timezone should I use?", "What is the intended time zone?"),
    "target": ("Which reminder should I change?", "Which existing reminder did you mean?"),
    "recurrence": ("Which repeat schedule and end condition should I use?", "How often should it repeat, and when should it end?"),
    "conflict": ("Which of the conflicting details should I use?", "Which instruction should I follow?"),
}

_REFUSAL_ALTERNATIVE = "I can’t create a reminder that would facilitate harm or misuse private information."


class Interpreter:
    def __init__(self, model: ModelClient):
        self.model = model

    async def interpret(
        self,
        request: InterpretRequest,
        *,
        clock: datetime | None = None,
        timezone_name: str | None = None,
    ) -> ModelOutcome:
        generate_structured = getattr(self.model, "generate_structured", None)
        target = explicit_target(request)
        safety_refusal = refusal_for_request(request.text)
        if safety_refusal is None and target is not None:
            safety_refusal = refusal_for_request(target.subject)
        if safety_refusal is not None:
            if generate_structured is None:
                return safety_refusal
            alternatives = (safety_refusal, safety_refusal.model_copy(update={"message": _REFUSAL_ALTERNATIVE}))
            return await self._generate_guided(
                generate_structured,
                "The safety guard blocked a request. Category: " + safety_refusal.category
                + ". Choose a brief, safe refusal. There is no reminder action.",
                alternatives,
            )

        reference_time = clock or request.reference_time or datetime.now(timezone.utc)
        trusted_timezone = timezone_name or request.timezone
        if generate_structured is not None:
            actions = ground_actions(request, reference_time, trusted_timezone)
            if actions is not None and len({action.model_dump_json() for action in actions}) == len(actions):
                proposed = ReminderResponse(outcome="reminder", actions=actions)
                return await self._generate_guided(
                    generate_structured,
                    "Return these request-grounded reminder actions using the required JSON contract. "
                    "The actions are proposals.\n" + proposed.model_dump_json(),
                    (proposed,),
                )
            unresolved = _unresolved_fields(request)
            if actions is not None:
                unresolved.add("conflict")
            fields = sorted(unresolved)
            if fields:
                questions = zip(*(_CLARIFICATION_QUESTIONS[field] for field in fields), strict=True)
                alternatives = tuple(
                    ClarificationResponse(outcome="clarification", question=" ".join(group), unresolved_fields=fields)
                    for group in questions
                )
                return await self._generate_guided(
                    generate_structured,
                    "Ask for these unresolved reminder fields: " + ", ".join(fields)
                    + ". Select one focused question. There is no reminder action.",
                    alternatives,
                )

        prompt = self._build_prompt(request, reference_time, trusted_timezone)
        try:
            outcome = _parse_reply(await self.model.generate(prompt))
            self._validate_outcome(outcome, request, trusted_timezone, reference_time)
        except (ValueError, TemporalValidationError) as exc:
            raise ServiceException(502, "INVALID_MODEL_OUTPUT", str(exc)) from exc
        return outcome

    @staticmethod
    async def _generate_guided(
        generate: StructuredGenerator, prompt: str, candidates: Sequence[ModelOutcome]
    ) -> ModelOutcome:
        values = [candidate.model_dump(mode="json") for candidate in candidates]
        properties = {}
        for field, value in values[0].items():
            alternatives = [item[field] for item in values]
            properties[field] = (
                {"const": value} if all(item == value for item in alternatives) else {"enum": alternatives}
            )
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
        outcome = _parse_reply(await generate(prompt, schema))
        if outcome.model_dump(mode="json") not in values:
            raise ServiceException(502, "INVALID_MODEL_OUTPUT", "Ollama returned output outside the grounded constraints.")
        return outcome

    @staticmethod
    def _build_prompt(
        request: InterpretRequest, clock: datetime, timezone_name: str | None
    ) -> str:
        context = [
            item.model_dump(mode="json") for item in request.reminder_context
            if refusal_for_request(item.subject) is None
        ]
        local_zone = ZoneInfo(timezone_name) if timezone_name else timezone.utc
        fields = _unresolved_fields(request)
        prompt = [
            f"Reference time (UTC): {clock.astimezone(timezone.utc).isoformat()}",
            f"Trusted timezone: {timezone_name or 'not supplied'}",
            f"Trusted reminder references: {json.dumps(context, ensure_ascii=False)}",
        ]
        if timezone_name:
            prompt.append(f"Reference time (local): {clock.astimezone(local_zone).isoformat()}")
        if fields:
            prompt.append(f"Unresolved fields detected: {', '.join(sorted(fields))}")
        if timezone_name:
            try:
                relative = resolve_relative_time(request.text, clock, timezone_name)
                if isinstance(relative, datetime):
                    prompt.append(f"Resolved elapsed time: {relative.astimezone(local_zone).isoformat()}")
                elif relative is not None:
                    prompt.append(f"Resolved calendar date: {relative.isoformat()}")
            except TemporalValidationError:
                prompt.append("The relative date is outside the supported calendar range.")
        prompt.append(
            "Request text (JSON string): " + json.dumps(request.text, ensure_ascii=False)
        )
        return "\n".join(prompt)

    @staticmethod
    def _validate_outcome(
        outcome: ModelOutcome,
        request: InterpretRequest,
        timezone_name: str | None,
        reference_time: datetime,
    ) -> None:
        if isinstance(outcome, ClarificationResponse):
            validate_clarification(request, outcome.unresolved_fields, justified=_unresolved_fields(request))
            return
        if isinstance(outcome, RefusalResponse):
            if refusal_for_request(request.text) is None:
                raise ValueError("refusal is not justified by a disallowed request")
            return
        if not isinstance(outcome, ReminderResponse):
            raise ValueError("unsupported model outcome")

        unresolved = _unresolved_fields(request)
        if unresolved:
            raise ValueError(
                "request is missing or ambiguous on: " + ", ".join(sorted(unresolved))
            )
        intended = _requested_intent(request.text)
        used_targets: set[str] = set()
        action_fingerprints: set[tuple[str, str, str, str | None]] = set()
        for action in outcome.actions:
            if refusal_for_request(action.subject) is not None:
                raise ValueError("action subject violates the safety guard")
            if intended and action.intent != intended:
                raise ValueError("action intent conflicts with the user's request")
            if timezone_name and action.timezone != timezone_name:
                raise ValueError("action timezone differs from trusted timezone")
            if timezone_name is None and not mentions_timezone(request.text):
                raise ValueError("action timezone is not supported by trusted or explicit context")
            local = validate_zoned_datetime(action.due_at, action.timezone)
            fingerprint = (
                action.intent,
                action.subject.casefold(),
                action.due_at.isoformat(),
                action.target_reference,
            )
            if fingerprint in action_fingerprints:
                raise ValueError("duplicate reminder actions are not allowed")
            action_fingerprints.add(fingerprint)
            _validate_explicit_timezone(request.text, action.timezone, local)
            _validate_explicit_slots(request.text, local, action.recurrence)
            _validate_dst_ambiguity(request.text, local, action.timezone)
            if (
                len(outcome.actions) == 1
                and action.recurrence is None
                and action.intent != "snooze"
            ):
                expected = resolve_relative_time(request.text, reference_time, action.timezone)
                observed = (
                    local.astimezone(timezone.utc)
                    if isinstance(expected, datetime)
                    else local.date()
                )
                if expected is not None and observed != expected:
                    raise ValueError("action due time differs from the relative schedule")

            if action.intent == "create":
                if action.target_reference is not None:
                    raise ValueError("create action must not identify an existing target")
                _validate_subject_supported(action.subject, request.text)
            else:
                target = resolve_target(action.target_reference, request.reminder_context)
                if target is None:
                    raise ValueError("reschedule and snooze require one unique trusted target")
                if refusal_for_request(target.subject) is not None:
                    raise ValueError("the selected reminder target violates the safety guard")
                if target.reference in used_targets:
                    raise ValueError("a trusted target cannot have conflicting actions")
                used_targets.add(target.reference)
                if len(request.reminder_context) > 1:
                    mentioned = [
                        item
                        for item in request.reminder_context
                        if item.subject.casefold() in request.text.casefold()
                        or item.reference.casefold() in request.text.casefold()
                    ]
                    if len(mentioned) != 1 or mentioned[0].reference != target.reference:
                        raise ValueError("request does not uniquely identify the trusted target")
                if target.subject.casefold() != action.subject.casefold():
                    raise ValueError("action subject differs from its trusted target")
                if action.intent == "snooze" and action.recurrence is not None:
                    raise ValueError("snooze must be a one-time action")
                if action.intent == "snooze":
                    duration = re.search(
                        r"\bfor\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(minute|hour|day)s?\b",
                        request.text,
                        re.I,
                    )
                    if duration:
                        amount_text = duration.group(1).casefold()
                        amount = (
                            int(amount_text)
                            if amount_text.isdigit()
                            else ("one two three four five six seven eight nine ten".split().index(amount_text) + 1)
                        )
                        unit = duration.group(2).casefold()
                        delta = {
                            "minute": timedelta(minutes=amount),
                            "hour": timedelta(hours=amount),
                            "day": timedelta(days=amount),
                        }[unit]
                        base = target.due_at or reference_time
                        expected_due = (base + delta).astimezone(action.due_at.tzinfo)
                        if action.due_at != expected_due:
                            raise ValueError("snooze due time does not match the stated duration")
                if action.intent == "reschedule" and target.recurrence is not None:
                    if action.recurrence != target.recurrence:
                        raise ValueError("reschedule must preserve the trusted recurrence")

            if action.recurrence is not None:
                if action.recurrence.timezone != action.timezone:
                    raise ValueError("recurrence timezone must match action timezone")
                validate_recurrence(action.recurrence, local.date())
                if action.recurrence.end_condition is None and not re.search(
                    r"\b(?:indefinitely|forever|no end date|without end)\b", request.text, re.I
                ):
                    raise ValueError("indefinite recurrence was not explicitly requested")
            elif re.search(r"\b(?:daily|weekly|monthly|yearly|annually|every)\b", request.text, re.I):
                raise ValueError("recurring request cannot return a one-time action")


def _parse_reply(reply: ModelReply) -> ModelOutcome:
    try:
        return OUTCOME_ADAPTER.validate_json(reply.content)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ServiceException(
            502, "INVALID_MODEL_OUTPUT", "Ollama returned output outside the required contract."
        ) from exc


def _unresolved_fields(request: InterpretRequest) -> set[str]:
    fields = justified_fields(request) | grounding_unresolved_fields(request)
    if explicit_target_unresolved(request):
        fields.add("target")
    return fields


def _requested_intent(text: str) -> str | None:
    if re.search(r"\b(?:snooze|postpone|delay)\b", text, re.I):
        return "snooze"
    if re.search(r"\b(?:reschedule|move|change the time)\b", text, re.I):
        return "reschedule"
    if re.search(r"\b(?:remind me|reminder|create|set up)\b", text, re.I):
        return "create"
    return None


def _validate_subject_supported(subject: str, text: str) -> None:
    ignored = {
        "a", "an", "and", "at", "for", "from", "me", "my", "of", "on",
        "please", "remind", "reminder", "the", "to", "with",
    }
    request_words = set(re.findall(r"[a-z0-9]+", text.casefold()))
    subject_words = {
        token
        for token in re.findall(r"[a-z0-9]+", subject.casefold())
        if token not in ignored
    }
    if not subject_words.issubset(request_words):
        raise ValueError("action subject introduces details not present in the request")


def _validate_explicit_slots(
    text: str, local: datetime, recurrence: Recurrence | None
) -> None:
    date_matches = list(re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text))
    if recurrence is not None:
        end_dates = {
            match.start(1): match.group(1)
            for match in re.finditer(r"\buntil\s+(\d{4}-\d{2}-\d{2})\b", text, re.I)
        }
        if end_dates:
            until = recurrence.end_condition.until if recurrence.end_condition else None
            if until is None or until.isoformat() not in end_dates.values():
                raise ValueError("recurrence end date differs from an explicitly stated end date")
            date_matches = [match for match in date_matches if match.start() not in end_dates]
    iso_dates = [match.group(0) for match in date_matches]
    if iso_dates and local.date().isoformat() not in iso_dates:
        raise ValueError("action date differs from an explicitly stated date")
    time_matches = list(
        re.finditer(
            r"(?:\bat\s+|\bT)(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I
        )
    )
    if date_matches and time_matches:
        selected_dates = [item for item in date_matches if item.group(0) == local.date().isoformat()]
        selected_positions = {item.start() for item in selected_dates}
        associated = []
        for time_match in time_matches:
            preceding = [item for item in date_matches if item.start() < time_match.start()]
            if preceding and preceding[-1].start() in selected_positions:
                associated.append(time_match)
        time_matches = associated or time_matches[:1] if len(date_matches) == 1 else associated
    for time_match in time_matches:
        hour_text, minute_text, meridiem = time_match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        if not 0 <= minute <= 59:
            continue
        if meridiem:
            if not 1 <= hour <= 12:
                continue
            hour = hour % 12 + (12 if meridiem.casefold() == "pm" else 0)
        if 0 <= hour <= 23 and (local.hour, local.minute) != (hour, minute):
            raise ValueError("action time differs from an explicitly stated time")


def _validate_dst_ambiguity(text: str, local: datetime, timezone_name: str) -> None:
    wall = local.replace(tzinfo=None)
    candidates = local_time_candidates(wall, timezone_name)
    if len(candidates) > 1 and not re.search(
        r"\b(?:UTC|GMT|[+-]\d{2}:?\d{2}|EST|EDT|CST|CDT|MST|MDT|PST|PDT)\b",
        text,
        re.I,
    ):
        raise ValueError("local time is ambiguous; clarification is required")


def _validate_explicit_timezone(
    text: str, timezone_name: str, local: datetime
) -> None:
    explicit_zone = re.search(
        r"\b(?:[A-Za-z_+-]+/)+[A-Za-z_+-]+\b", text
    )
    if explicit_zone and explicit_zone.group(0) != timezone_name:
        raise ValueError("action timezone differs from explicitly stated IANA timezone")
    named_zones = {
        "new york": "America/New_York",
        "london": "Europe/London",
        "los angeles": "America/Los_Angeles",
        "tokyo": "Asia/Tokyo",
        "paris": "Europe/Paris",
    }
    for label, zone in named_zones.items():
        if label in text.casefold() and timezone_name != zone:
            raise ValueError("action timezone differs from explicitly stated location")
    abbreviations = re.findall(r"\b(?:UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT)\b", text, re.I)
    if abbreviations:
        names = {item.upper() for item in abbreviations}
        is_utc = local.utcoffset() is not None and local.utcoffset().total_seconds() == 0
        if not (is_utc and names.intersection({"UTC", "GMT"})) and local.tzname() not in names:
            raise ValueError("action timezone does not match explicit timezone abbreviation")
