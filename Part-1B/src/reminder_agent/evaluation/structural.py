"""Strict structural evaluation without repair or coercion."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from reminder_agent.contracts.models import OUTCOME_ADAPTER


def validate_structure(raw: str | dict[str, Any]) -> tuple[bool, Any, str | None]:
    try:
        outcome = (
            OUTCOME_ADAPTER.validate_json(raw)
            if isinstance(raw, str)
            else OUTCOME_ADAPTER.validate_python(raw)
        )
        return True, outcome, None
    except (ValidationError, ValueError, TypeError) as exc:
        return False, None, str(exc)
