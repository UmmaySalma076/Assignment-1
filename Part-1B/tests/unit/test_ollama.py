import asyncio
import json

import httpx
import pytest

from reminder_agent.api.errors import ServiceException
from reminder_agent.config import PINNED_MODEL, Settings
from reminder_agent.services.ollama import OllamaClient


def test_chat_uses_pinned_model_json_schema_and_non_streaming_local_endpoint():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/api/chat":
            payload = json.loads(request.content)
            assert payload["model"] == PINNED_MODEL
            assert payload["stream"] is False
            assert isinstance(payload["format"], dict)
            assert payload["options"]["temperature"] == 0.2
            return httpx.Response(200, json={
                "message": {"content": '{"outcome":"refusal","category":"unsafe_action","message":"No."}'}
            })
        return httpx.Response(200, json={
            "models": [{"name": PINNED_MODEL, "digest": "sha256:example"}]
        })

    async def run():
        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="http://127.0.0.1:11434",
            transport=transport,
        )
        adapter = OllamaClient(Settings(), client)
        try:
            reply = await adapter.generate("test prompt")
            return reply
        finally:
            await adapter.close()

    reply = asyncio.run(run())
    assert reply.model_tag == PINNED_MODEL
    assert reply.model_digest == "sha256:example"
    assert reply.generation_settings["temperature"] == 0.2
    assert len(calls) == 2


def test_health_requires_the_pinned_model_to_be_present():
    async def run():
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"models": []})
        )
        client = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=transport)
        adapter = OllamaClient(Settings(), client)
        try:
            return await adapter.health()
        finally:
            await adapter.close()

    assert asyncio.run(run()) is False


def test_connection_error_maps_to_local_service_unavailable():
    def handler(_request):
        raise httpx.ConnectError("unavailable")

    async def run():
        client = httpx.AsyncClient(
            base_url="http://127.0.0.1:11434",
            transport=httpx.MockTransport(handler),
        )
        adapter = OllamaClient(Settings(), client)
        try:
            with pytest.raises(ServiceException) as error:
                await adapter.generate("prompt")
            return error.value
        finally:
            await adapter.close()

    error = asyncio.run(run())
    assert error.status_code == 503
    assert error.code == "OLLAMA_UNAVAILABLE"
