import json

from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.config import Settings
from reminder_agent.services.ollama import ModelReply


class StubModel:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def generate(self, prompt):
        self.calls.append(prompt)
        return ModelReply(self.content, "tinyllama:1.1b-chat-v0.6-q4_0", "digest", {}, prompt)


def test_explicit_create_preserves_subject_and_details_without_claiming_storage():
    model = StubModel(json.dumps({
        "outcome": "reminder",
        "actions": [{
            "intent": "create",
            "subject": "call the dentist",
            "due_at": "2026-03-05T09:30:00-05:00",
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": None,
        }],
    }))
    client = TestClient(create_app(Settings(), model))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Remind me to call the dentist on 2026-03-05 at 9:30 AM.",
        "timezone": "America/New_York",
    })
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["subject"] == "call the dentist"
    assert "persisted" not in response.text.casefold()
    assert len(model.calls) == 1
    client.close()


def test_controlled_reference_clock_supports_relative_interpretation():
    model = StubModel(json.dumps({
        "outcome": "reminder",
        "actions": [{
            "intent": "create",
            "subject": "take a break",
            "due_at": "2026-03-01T09:00:00-05:00",
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": None,
        }],
    }))
    settings = Settings(allow_evaluation_context=True)
    client = TestClient(create_app(settings, model))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Remind me to take a break in two hours.",
        "timezone": "America/New_York",
        "reference_time": "2026-03-01T12:00:00Z",
    })
    assert response.status_code == 200
    assert response.json()["actions"][0]["due_at"].startswith("2026-03-01T09:00:00")
    assert "saved" not in response.text.casefold()
    assert len(model.calls) == 1
    client.close()


def test_multiple_explicit_actions_remain_distinct():
    model = StubModel(json.dumps({
        "outcome": "reminder",
        "actions": [
            {"intent":"create","subject":"call Alex","due_at":"2026-03-05T09:00:00-05:00","timezone":"America/New_York","recurrence":None,"target_reference":None},
            {"intent":"create","subject":"buy milk","due_at":"2026-03-06T18:00:00-05:00","timezone":"America/New_York","recurrence":None,"target_reference":None},
        ],
    }))
    client = TestClient(create_app(Settings(), model))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Remind me to call Alex on 2026-03-05 at 9:00 AM and to buy milk on 2026-03-06 at 6:00 PM.",
        "timezone": "America/New_York",
    })
    assert response.status_code == 200, response.text
    assert len(response.json()["actions"]) == 2
    client.close()


def test_invalid_model_output_is_not_rewritten_as_clarification():
    model = StubModel('{"outcome":"reminder","actions":[]}')
    client = TestClient(create_app(Settings(), model))
    response = client.post("/v1/reminders/interpret", json={"text": "Remind me to call home."})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
    client.close()
