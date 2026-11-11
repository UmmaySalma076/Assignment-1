"""Resolution of targets exclusively within caller-supplied trusted context."""

from __future__ import annotations

from reminder_agent.contracts.models import ReminderReference


def resolve_target(
    reference: str | None, context: list[ReminderReference]
) -> ReminderReference | None:
    if reference is None:
        return None
    matches = [item for item in context if item.reference == reference]
    return matches[0] if len(matches) == 1 else None


def find_target_candidates(
    subject: str, context: list[ReminderReference]
) -> list[ReminderReference]:
    normalized = subject.casefold().strip()
    return [item for item in context if item.subject.casefold().strip() == normalized]
