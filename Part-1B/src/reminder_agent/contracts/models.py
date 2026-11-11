"""Strict Pydantic contracts shared by the API and local model."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def parse_rfc3339(value: datetime | str | None, field_name: str) -> datetime | None:
    if isinstance(value, str):
        if not RFC3339_DATETIME.fullmatch(value):
            raise ValueError(f"{field_name} must be an RFC 3339 datetime with an offset")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid RFC 3339 datetime") from exc
    return value


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReminderReference(StrictModel):
    reference: NonEmpty
    subject: NonEmpty
    due_at: datetime | None = None
    timezone: str | None = None
    recurrence: Recurrence | None = None

    @field_validator("due_at", mode="before")
    @classmethod
    def parse_due_at(cls, value: datetime | str | None) -> datetime | None:
        return parse_rfc3339(value, "due_at")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        return validate_timezone(value) if value is not None else None

    @field_validator("due_at")
    @classmethod
    def due_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("due_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def context_time_matches_timezone(self) -> ReminderReference:
        if self.due_at is not None and self.timezone is not None:
            local = self.due_at.astimezone(ZoneInfo(self.timezone))
            if local.utcoffset() != self.due_at.utcoffset():
                raise ValueError("due_at offset does not match reminder timezone")
        return self


class RecurrenceEnd(StrictModel):
    until: date | None = None
    occurrences: int | None = Field(default=None, ge=1)

    @field_validator("until", mode="before")
    @classmethod
    def parse_until(cls, value: date | str | None) -> date | None:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("until must be a valid ISO calendar date") from exc
        return value

    @model_validator(mode="after")
    def exactly_one_end_selector(self) -> RecurrenceEnd:
        if (self.until is None) == (self.occurrences is None):
            raise ValueError("exactly one of until or occurrences is required")
        return self


class Recurrence(StrictModel):
    frequency: Literal["daily", "weekly", "monthly", "yearly"]
    interval: int = Field(ge=1)
    weekdays: list[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]] | None
    day_of_month: int | None = Field(ge=1, le=31)
    month: int | None = Field(ge=1, le=12)
    day: int | None = Field(ge=1, le=31)
    timezone: str
    end_condition: RecurrenceEnd | None

    @field_validator("weekdays")
    @classmethod
    def unique_weekdays(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("weekdays must not contain duplicates")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return validate_timezone(value)

    @model_validator(mode="after")
    def selectors_match_frequency(self) -> Recurrence:
        expected = {
            "daily": (False, False, False, False),
            "weekly": (True, False, False, False),
            "monthly": (False, True, False, False),
            "yearly": (False, False, True, True),
        }[self.frequency]
        present = (
            self.weekdays is not None,
            self.day_of_month is not None,
            self.month is not None,
            self.day is not None,
        )
        if present != expected:
            raise ValueError("recurrence selectors do not match frequency")
        if self.frequency == "weekly" and not self.weekdays:
            raise ValueError("weekly recurrence requires at least one weekday")
        if self.frequency == "yearly":
            try:
                date(2000, self.month, self.day)
            except ValueError as exc:
                raise ValueError("yearly month/day is invalid") from exc
        return self


class InterpretRequest(StrictModel):
    text: NonEmpty = Field(max_length=2000)
    timezone: str | None = None
    reference_time: datetime | None = None
    reminder_context: list[ReminderReference] = Field(default_factory=list)

    @field_validator("reference_time", mode="before")
    @classmethod
    def parse_reference_time(cls, value: datetime | str | None) -> datetime | None:
        return parse_rfc3339(value, "reference_time")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        return validate_timezone(value) if value is not None else None

    @field_validator("reference_time")
    @classmethod
    def reference_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("reference_time must include a UTC offset")
        return value

    @model_validator(mode="after")
    def reminder_references_are_unique(self) -> InterpretRequest:
        references = [item.reference for item in self.reminder_context]
        if len(references) != len(set(references)):
            raise ValueError("reminder reference identifiers must be unique")
        return self


class ReminderAction(StrictModel):
    intent: Literal["create", "reschedule", "snooze"]
    subject: NonEmpty
    due_at: datetime
    timezone: str
    recurrence: Recurrence | None
    target_reference: NonEmpty | None

    @field_validator("due_at", mode="before")
    @classmethod
    def parse_due_at(cls, value: datetime | str) -> datetime:
        parsed = parse_rfc3339(value, "due_at")
        if parsed is None:
            raise ValueError("due_at is required")
        return parsed

    @field_validator("due_at")
    @classmethod
    def due_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("due_at must include a UTC offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return validate_timezone(value)


class ReminderResponse(StrictModel):
    outcome: Literal["reminder"]
    actions: list[ReminderAction] = Field(min_length=1)


class ClarificationResponse(StrictModel):
    outcome: Literal["clarification"]
    question: NonEmpty
    unresolved_fields: list[NonEmpty] = Field(min_length=1)


class RefusalResponse(StrictModel):
    outcome: Literal["refusal"]
    category: Literal[
        "imminent_harm",
        "self_harm",
        "violence",
        "sensitive_personal_information",
        "unsafe_action",
    ]
    message: NonEmpty


ModelOutcome = Annotated[
    ReminderResponse | ClarificationResponse | RefusalResponse,
    Field(discriminator="outcome"),
]
OUTCOME_ADAPTER = TypeAdapter(ModelOutcome)


class ErrorDetail(StrictModel):
    code: Literal[
        "INVALID_REQUEST",
        "INVALID_MODEL_OUTPUT",
        "OLLAMA_UNAVAILABLE",
        "OLLAMA_TIMEOUT",
        "INTERNAL_ERROR",
    ]
    message: NonEmpty


class ServiceError(StrictModel):
    error: ErrorDetail
