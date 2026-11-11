"""Validated runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

PINNED_MODEL = "tinyllama:1.1b-chat-v0.6-q4_0"


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = "http://127.0.0.1:11434"
    model: str = PINNED_MODEL
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 120.0
    max_request_chars: int = 2000
    allow_evaluation_context: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.ollama_base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("Ollama must be an absolute local HTTP(S) endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OLLAMA_BASE_URL must not include credentials or query parameters")
        if self.model != PINNED_MODEL:
            raise ValueError(f"model must be pinned to {PINNED_MODEL}")
        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise ValueError("Ollama timeouts must be positive")
        if not 1 <= self.max_request_chars <= 2000:
            raise ValueError("MAX_REQUEST_CHARS must be between 1 and 2000")

    @classmethod
    def from_env(cls) -> Settings:
        model = os.getenv("OLLAMA_MODEL", PINNED_MODEL)
        if model != PINNED_MODEL:
            raise ValueError(f"OLLAMA_MODEL must be pinned to {PINNED_MODEL}")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("OLLAMA_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Ollama must be hosted on this machine")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OLLAMA_BASE_URL must not include credentials or query parameters")

        connect = _positive_float("OLLAMA_CONNECT_TIMEOUT_SECONDS", 5.0)
        read = _positive_float("OLLAMA_READ_TIMEOUT_SECONDS", 120.0)
        max_chars = _integer("MAX_REQUEST_CHARS", 2000)
        if not 1 <= max_chars <= 2000:
            raise ValueError("MAX_REQUEST_CHARS must be between 1 and 2000")
        return cls(
            ollama_base_url=base_url,
            connect_timeout_seconds=connect,
            read_timeout_seconds=read,
            max_request_chars=max_chars,
        )


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
