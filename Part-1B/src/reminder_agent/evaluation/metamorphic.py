"""Deterministic transformations and relations for reminder proposals."""

from __future__ import annotations

from typing import Any

from reminder_agent.contracts.models import ReminderResponse


def normalized_meaning(outcome: Any) -> tuple[Any, ...] | None:
    if not isinstance(outcome, ReminderResponse):
        return None
    return tuple(
        (
            action.intent,
            action.subject.casefold().strip(),
            action.due_at.isoformat(),
            action.timezone,
            action.recurrence.model_dump(mode="json") if action.recurrence else None,
            action.target_reference,
        )
        for action in outcome.actions
    )


def compare_equivalent(left: Any, right: Any) -> bool:
    return normalized_meaning(left) == normalized_meaning(right) and normalized_meaning(left) is not None


def time_only_change(
    before: dict[str, Any], after: dict[str, Any], allowed_fields: list[str]
) -> bool:
    ignored = set(allowed_fields)
    return all(
        key == "due_at" or key in ignored or before.get(key) == after.get(key)
        for key in before.keys() | after.keys()
    )
