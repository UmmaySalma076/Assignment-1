import json

from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.config import Settings
from reminder_agent.services.ollama import ModelReply


class StubModel:
    def __init__(self, content):
        self.content = content

    async def generate(self, prompt):
        return ModelReply(self.content, "tinyllama:1.1b-chat-v0.6-q4_0", None, {}, prompt)


def test_reschedule_uses_one_unique_reference_without_mutating_context():
    context = [{
        "reference": "r-1",
        "subject": "dentist appointment",
        "due_at": "2026-03-05T09:00:00-05:00",
        "timezone": "America/New_York",
    }]
    payload = {
        "outcome": "reminder",
        "actions": [{
            "intent": "reschedule",
            "subject": "dentist appointment",
            "due_at": "2026-03-06T10:00:00-05:00",
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": "r-1",
        }],
    }
    client = TestClient(create_app(Settings(), StubModel(json.dumps(payload))))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Reschedule my dentist appointment to 2026-03-06 at 10:00 AM.",
        "timezone": "America/New_York",
        "reminder_context": context,
    })
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["target_reference"] == "r-1"
    assert context[0]["due_at"] == "2026-03-05T09:00:00-05:00"
    client.close()


def test_snooze_is_one_time_and_duration_is_deterministic():
    context = [{
        "reference": "r-1",
        "subject": "dentist appointment",
        "due_at": "2026-03-01T08:00:00-05:00",
        "timezone": "America/New_York",
    }]
    payload = {
        "outcome": "reminder",
        "actions": [{
            "intent": "snooze",
            "subject": "dentist appointment",
            "due_at": "2026-03-01T10:00:00-05:00",
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": "r-1",
        }],
    }
    client = TestClient(create_app(Settings(), StubModel(json.dumps(payload))))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Snooze my dentist appointment for 2 hours.",
        "timezone": "America/New_York",
        "reminder_context": context,
    })
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["due_at"].startswith("2026-03-01T10:00:00")
    client.close()


def test_non_unique_target_is_not_guessed_from_context():
    context = [
        {"reference": "r-1", "subject": "dentist appointment", "timezone": "America/New_York"},
        {"reference": "r-2", "subject": "doctor appointment", "timezone": "America/New_York"},
    ]
    payload = {
        "outcome": "reminder",
        "actions": [{
            "intent": "reschedule",
            "subject": "dentist appointment",
            "due_at": "2026-03-06T10:00:00-05:00",
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": "r-1",
        }],
    }
    client = TestClient(create_app(Settings(), StubModel(json.dumps(payload))))
    response = client.post("/v1/reminders/interpret", json={
        "text": "Reschedule my appointment to 2026-03-06 at 10:00 AM.",
        "timezone": "America/New_York",
        "reminder_context": context,
    })
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
    client.close()
