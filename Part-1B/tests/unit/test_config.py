import pytest

from reminder_agent.config import PINNED_MODEL, Settings


def test_default_settings_pin_model_and_request_limit(monkeypatch):
    for key in (
        "MAX_REQUEST_CHARS",
        "OLLAMA_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_CONNECT_TIMEOUT_SECONDS",
        "OLLAMA_READ_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert settings.max_request_chars == 2000
    assert settings.model == PINNED_MODEL
    assert settings.connect_timeout_seconds == 5
    assert settings.read_timeout_seconds == 120


@pytest.mark.parametrize("value", ["1", "2000"])
def test_request_limit_accepts_inclusive_bounds(monkeypatch, value):
    monkeypatch.setenv("MAX_REQUEST_CHARS", value)
    assert Settings.from_env().max_request_chars == int(value)


@pytest.mark.parametrize("value", ["0", "2001", "-1", "not-a-number"])
def test_request_limit_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("MAX_REQUEST_CHARS", value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_model_tag_cannot_be_overridden(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "tinyllama:latest")
    with pytest.raises(ValueError, match="pinned"):
        Settings.from_env()


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "not a url",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434?token=secret",
    ],
)
def test_ollama_endpoint_must_be_local(monkeypatch, url):
    monkeypatch.setenv("OLLAMA_BASE_URL", url)
    with pytest.raises(ValueError):
        Settings.from_env()
