"""Local-only asynchronous Ollama client."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from reminder_agent.config import PINNED_MODEL, Settings
from reminder_agent.contracts.models import OUTCOME_ADAPTER
from reminder_agent.api.errors import ServiceException

PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "reminder_system.txt"
GENERATION_SETTINGS: dict[str, Any] = {
    "temperature": 0.2,
    "top_p": 0.9,
}


@dataclass(frozen=True)
class ModelReply:
    content: str
    model_tag: str
    model_digest: str | None
    generation_settings: dict[str, Any]
    prompt: str


class OllamaClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout_seconds,
                read=settings.read_timeout_seconds,
                write=settings.read_timeout_seconds,
                pool=settings.connect_timeout_seconds,
            ),
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            if not response.is_success:
                return False
            payload = response.json()
            return any(
                model.get("name") == PINNED_MODEL
                for model in payload.get("models", [])
                if isinstance(model, dict)
            )
        except httpx.TimeoutException as exc:
            raise ServiceException(504, "OLLAMA_TIMEOUT", "Local Ollama timed out.") from exc
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Local Ollama is unavailable.") from exc

    async def generate(self, prompt: str) -> ModelReply:
        if self.settings.model != PINNED_MODEL:
            raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Pinned local model is not configured.")
        system = PROMPT_PATH.read_text(encoding="utf-8")
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": PINNED_MODEL,
                    "stream": False,
                    "format": OUTCOME_ADAPTER.json_schema(),
                    "options": GENERATION_SETTINGS,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ServiceException(504, "OLLAMA_TIMEOUT", "Local Ollama timed out.") from exc
        except httpx.ConnectError as exc:
            raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Local Ollama is unavailable.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 or exc.response.status_code == 404:
                raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Pinned local model is unavailable.") from exc
            raise ServiceException(502, "INVALID_MODEL_OUTPUT", "Ollama returned an invalid response.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceException(502, "INVALID_MODEL_OUTPUT", "Ollama returned an invalid response.") from exc

        message = payload.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ServiceException(502, "INVALID_MODEL_OUTPUT", "Ollama returned empty model output.")
        digest = await self._find_model_digest()
        return ModelReply(
            content=content,
            model_tag=PINNED_MODEL,
            model_digest=digest,
            generation_settings=dict(GENERATION_SETTINGS),
            prompt=prompt,
        )

    async def _find_model_digest(self) -> str | None:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            for model in models:
                if model.get("name") == PINNED_MODEL:
                    return model.get("digest")
        except (httpx.HTTPError, ValueError, AttributeError):
            return None
        return None
