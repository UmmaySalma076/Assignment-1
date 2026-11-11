"""Deterministic semantic rubric evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from reminder_agent.contracts.models import (
    ClarificationResponse,
    RefusalResponse,
    ReminderResponse,
)


def score_semantics(outcome: Any, case: dict[str, Any]) -> dict[str, bool]:
    if outcome is None:
        return {criterion: False for criterion in case.get("semantic_criteria", [])}
    expected = case["expected_outcome"]
    actual = outcome.outcome
    result: dict[str, bool] = {}
    if "intent_outcome" in case.get("semantic_criteria", []):
        result["intent_outcome"] = actual == expected
        if expected == "reminder" and isinstance(outcome, ReminderResponse):
            intents = {item.get("intent") for item in case.get("expected_actions", [])}
            result["intent_outcome"] = all(action.intent in intents for action in outcome.actions) if intents else True
    if "explicit_details" in case.get("semantic_criteria", []):
        result["explicit_details"] = _actions_match(outcome, case, details=True)
    if "temporal_correctness" in case.get("semantic_criteria", []):
        result["temporal_correctness"] = _actions_match(outcome, case, details=False)
    if "clarification" in case.get("semantic_criteria", []):
        fields = set(getattr(outcome, "unresolved_fields", []))
        result["clarification"] = (
            isinstance(outcome, ClarificationResponse)
            and set(case.get("expected_unresolved_fields", [])).issubset(fields)
        )
    if "refusal_safety" in case.get("semantic_criteria", []):
        result["refusal_safety"] = (
            isinstance(outcome, RefusalResponse)
            and outcome.category == case.get("expected_refusal_category")
        )
    if "assumption_control" in case.get("semantic_criteria", []):
        result["assumption_control"] = (
            (
                expected == "reminder"
                and isinstance(outcome, ReminderResponse)
                and _actions_match(outcome, case, details=True)
            )
            or (expected == "clarification" and isinstance(outcome, ClarificationResponse))
            or (expected == "refusal" and isinstance(outcome, RefusalResponse))
        )
    if "multi_action_fidelity" in case.get("semantic_criteria", []):
        result["multi_action_fidelity"] = (
            isinstance(outcome, ReminderResponse)
            and len(outcome.actions) == case.get("expected_action_count")
            and _actions_match(outcome, case, details=True)
        )
    if "metamorphic_relation" in case.get("semantic_criteria", []):
        result["metamorphic_relation"] = isinstance(outcome, ReminderResponse)
    return result


def _actions_match(outcome: Any, case: dict[str, Any], details: bool) -> bool:
    if not isinstance(outcome, ReminderResponse):
        return False
    expected_actions = case.get("expected_actions", [])
    if len(expected_actions) != len(outcome.actions):
        return False
    for actual, expected in zip(outcome.actions, expected_actions, strict=True):
        fields = ("intent", "subject", "timezone", "target_reference") if details else ()
        for field in fields:
            if field in expected and getattr(actual, field) != expected[field]:
                return False
        if "due_at" in expected:
            try:
                if actual.due_at != datetime.fromisoformat(expected["due_at"]):
                    return False
            except ValueError:
                return False
        if details and "recurrence" in expected:
            expected_recurrence = expected["recurrence"]
            if (expected_recurrence is None) != (actual.recurrence is None):
                return False
            if expected_recurrence is not None:
                actual_recurrence = actual.recurrence.model_dump(mode="json")
                if not _is_subset(expected_recurrence, actual_recurrence):
                    return False
    return True


def _is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return all(
            field in actual and _is_subset(value, actual[field])
            for field, value in expected.items()
        )
    return expected == actual
