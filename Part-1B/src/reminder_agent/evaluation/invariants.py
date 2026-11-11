"""Deterministic cross-field and requirement invariant checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from reminder_agent.contracts.models import (
    ClarificationResponse,
    RefusalResponse,
    ReminderResponse,
)
from reminder_agent.domain.recurrence import validate_recurrence
from reminder_agent.domain.time import validate_zoned_datetime


def check_invariants(outcome: Any, case: dict[str, Any]) -> dict[str, bool]:
    checks = {"schema": outcome is not None}
    if outcome is None:
        return checks
    expected = case.get("expected_outcome")
    if isinstance(outcome, (ClarificationResponse, RefusalResponse)):
        checks["no_actions"] = not hasattr(outcome, "actions")
        if expected == "clarification":
            expected_fields = set(case.get("expected_unresolved_fields", []))
            checks["clarification_fields"] = expected_fields.issubset(
                {item.casefold() for item in outcome.unresolved_fields}
            )
        if expected == "refusal":
            checks["refusal_category"] = outcome.category == case.get("expected_refusal_category")
        return checks
    if not isinstance(outcome, ReminderResponse):
        checks["outcome_kind"] = False
        return checks

    checks["action_count"] = len(outcome.actions) == case.get("expected_action_count")
    trusted = case.get("trusted_context", {}).get("reminder_context", [])
    for action in outcome.actions:
        try:
            local = validate_zoned_datetime(action.due_at, action.timezone)
            if action.recurrence:
                validate_recurrence(action.recurrence, local.date())
            checks["time_zone_offset"] = checks.get("time_zone_offset", True)
        except ValueError:
            checks["time_zone_offset"] = False
        if action.intent == "create":
            checks["action_target"] = checks.get("action_target", True) and action.target_reference is None
        else:
            matches = [item for item in trusted if item.get("reference") == action.target_reference]
            checks["action_target"] = checks.get("action_target", True) and len(matches) == 1
            if action.intent == "snooze":
                checks["no_snooze_recurrence"] = action.recurrence is None

    expected_actions = case.get("expected_actions", [])
    for index, expected_action in enumerate(expected_actions):
        if index >= len(outcome.actions):
            checks["explicit_slots"] = False
            break
        actual = outcome.actions[index]
        for field in ("intent", "subject", "timezone", "target_reference"):
            if field in expected_action and getattr(actual, field) != expected_action[field]:
                checks["explicit_slots"] = False
        if "due_at" in expected_action:
            expected_time = datetime.fromisoformat(expected_action["due_at"])
            if actual.due_at != expected_time:
                checks["explicit_slots"] = False
        if "recurrence" in expected_action:
            expected_recurrence = expected_action["recurrence"]
            if expected_recurrence is None and actual.recurrence is not None:
                checks["explicit_slots"] = False
            elif expected_recurrence and actual.recurrence is None:
                checks["explicit_slots"] = False
    checks.setdefault("explicit_slots", True)
    return checks
