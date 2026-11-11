import json

import pytest
from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.api.errors import ServiceException
from reminder_agent.config import Settings
from reminder_agent.services.ollama import ModelReply


class StubModel:
    def __init__(self, result):
        self.result = result

    async def generate(self, prompt):
        if isinstance(self.result, Exception):
            raise self.result
        return ModelReply(self.result, "tinyllama:1.1b-chat-v0.6-q4_0", None, {}, prompt)


@pytest.mark.parametrize(
    ("result", "status", "code"),
    [
        ("not json", 502, "INVALID_MODEL_OUTPUT"),
        ('{"outcome":"reminder","actions":[]}', 502, "INVALID_MODEL_OUTPUT"),
        (
            json.dumps({"outcome":"reminder","actions":[{
                "intent":"create","subject":"call","due_at":"2026-03-05T09:00:00+00:00",
                "timezone":"America/New_York","recurrence":None,"target_reference":None,
            }]}),
            502,
            "INVALID_MODEL_OUTPUT",
        ),
        (ServiceException(503, "OLLAMA_UNAVAILABLE", "offline"), 503, "OLLAMA_UNAVAILABLE"),
        (ServiceException(504, "OLLAMA_TIMEOUT", "slow"), 504, "OLLAMA_TIMEOUT"),
    ],
)
def test_service_errors_are_explicit_and_never_success_shaped(result, status, code):
    client = TestClient(create_app(Settings(), StubModel(result)))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Remind me to call home on 2026-03-05 at 9:00 AM UTC."
    })
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "outcome" not in response.json()
    assert "actions" not in response.json()
    client.close()
