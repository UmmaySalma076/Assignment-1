from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    completed: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed


class TaskStatusUpdate(BaseModel):
    completed: bool


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)
