import json

import pytest
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


@pytest.mark.parametrize("correct_time", [True, False], ids=["correct", "incorrect"])
@pytest.mark.parametrize(
    ("schedule", "correct_due_at", "incorrect_due_at"),
    [
        ("in two hours", "2026-03-08T04:30:00-04:00", "2026-03-08T03:30:00-04:00"),
        ("in one month at 8:00 AM", "2026-04-08T08:00:00-04:00", "2026-04-09T08:00:00-04:00"),
        ("in ten months at 9:00 AM", "2027-01-08T09:00:00-05:00", "2026-12-08T09:00:00-05:00"),
    ],
    ids=["elapsed-across-dst", "calendar-month", "calendar-year-boundary"],
)
def test_relative_schedule_must_match_reference_clock(
    schedule, correct_due_at, incorrect_due_at, correct_time
):
    model = StubModel(json.dumps({
        "outcome": "reminder",
        "actions": [{
            "intent": "create",
            "subject": "check the calendar",
            "due_at": correct_due_at if correct_time else incorrect_due_at,
            "timezone": "America/New_York",
            "recurrence": None,
            "target_reference": None,
        }],
    }))
    with TestClient(create_app(Settings(allow_evaluation_context=True), model)) as client:
        response = client.post("/v1/reminders/interpret", json={
            "text": f"Remind me to check the calendar {schedule}.",
            "timezone": "America/New_York",
            "reference_time": "2026-03-08T06:30:00Z",
        })
    assert response.status_code == (200 if correct_time else 502), response.text
    if not correct_time:
        assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"


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


@pytest.mark.parametrize(
    ("start_text", "due_date", "until_date", "expected_status"),
    [
        ("", "2026-03-02", "2026-04-13", 200),
        (" starting 2026-03-02", "2026-03-02", "2026-04-13", 200),
        (" starting 2026-03-02", "2026-03-02", "2026-04-20", 502),
        (" starting 2026-03-02", "2026-04-13", "2026-04-13", 502),
    ],
)
def test_weekly_recurrence_distinguishes_start_and_end_dates(
    start_text, due_date, until_date, expected_status
):
    model = StubModel(json.dumps({
        "outcome": "reminder",
        "actions": [{
            "intent": "create",
            "subject": "review the schedule",
            "due_at": f"{due_date}T08:00:00+00:00",
            "timezone": "UTC",
            "recurrence": {
                "frequency": "weekly",
                "interval": 1,
                "weekdays": ["MO"],
                "day_of_month": None,
                "month": None,
                "day": None,
                "timezone": "UTC",
                "end_condition": {"until": until_date},
            },
            "target_reference": None,
        }],
    }))
    with TestClient(create_app(Settings(), model)) as client:
        response = client.post("/v1/reminders/interpret", json={
            "text": (
                f"Remind me to review the schedule every Monday{start_text} "
                "at 8:00 AM UTC until 2026-04-13."
            ),
            "timezone": "UTC",
        })
    assert response.status_code == expected_status, response.text
    if expected_status == 200:
        assert response.json()["actions"][0]["recurrence"]["end_condition"]["until"] == until_date
    else:
        assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"


def test_invalid_model_output_is_not_rewritten_as_clarification():
    model = StubModel('{"outcome":"reminder","actions":[]}')
    client = TestClient(create_app(Settings(), model))
    response = client.post("/v1/reminders/interpret", json={"text": "Remind me to call home."})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
    client.close()
