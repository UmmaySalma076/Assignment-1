from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    completed: StrictBool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> TaskUpdate:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title must not be null.")
        if "completed" in self.model_fields_set and self.completed is None:
            raise ValueError("Completed must be a boolean.")
        return self


class TaskReplace(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    completed: StrictBool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return value.strip()


class TaskStatusUpdate(BaseModel):
    completed: StrictBool


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    completed: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)
