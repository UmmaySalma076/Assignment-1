import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.config import PINNED_MODEL, Settings
from reminder_agent.services.ollama import ModelReply


class RecordingModel:
    def __init__(self, response):
        self.response = response
        self.structured_calls = []
        self.open_calls = []

    async def generate_structured(self, prompt, output_schema):
        self.structured_calls.append((prompt, output_schema))
        response = self.response(output_schema) if callable(self.response) else self.response
        return self._reply(prompt, response)

    async def generate(self, prompt):
        self.open_calls.append(prompt)
        return self._reply(prompt, self.response)

    @staticmethod
    def _reply(prompt, response):
        content = response if isinstance(response, str) else json.dumps(response)
        return ModelReply(content, PINNED_MODEL, None, {}, prompt)


def post_interpret(model, text, timezone="Asia/Kolkata"):
    with TestClient(create_app(Settings(), model)) as client:
        return client.post(
            "/v1/reminders/interpret", json={"text": text, "timezone": timezone}
        )


def folder_reminder(subject="label the blue folders"):
    return {
        "outcome": "reminder",
        "actions": [{
            "intent": "create",
            "subject": subject,
            "due_at": "2027-02-16T16:45:00+05:30",
            "timezone": "Asia/Kolkata",
            "recurrence": None,
            "target_reference": None,
        }],
    }


def choose_last_allowed_output(schema):
    return {
        field: rule["const"] if "const" in rule else rule["enum"][-1]
        for field, rule in schema["properties"].items()
    }


@pytest.mark.parametrize(
    ("model_output", "expected_status"),
    [
        (folder_reminder(), 200),
        (folder_reminder("label the folders"), 502),
        ('{"outcome":"reminder",', 502),
    ],
    ids=["grounded", "source-detail-omitted", "malformed"],
)
def test_grounded_create_checks_the_actual_model_proposal(model_output, expected_status):
    model = RecordingModel(model_output)
    response = post_interpret(
        model, "Remind me to label the blue folders on 2027-02-16 at 4:45 PM."
    )

    assert len(model.structured_calls) == 1
    assert model.open_calls == []
    _, schema = model.structured_calls[0]
    assert "label the blue folders" in json.dumps(schema)
    assert "2027-02-16T16:45:00+05:30" in json.dumps(schema)
    assert response.status_code == expected_status, response.text
    if expected_status == 502:
        assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
        assert "actions" not in response.json()
    else:
        action = response.json()["actions"][0]
        assert action["subject"] == "label the blue folders"
        assert datetime.fromisoformat(action["due_at"]) == datetime.fromisoformat(
            "2027-02-16T16:45:00+05:30"
        )


def test_ambiguous_request_can_return_the_model_selected_question():
    def pick_alternative(schema):
        properties = schema["properties"]
        options = properties["question"]["enum"]
        assert len(set(options)) > 1
        return {
            "outcome": properties["outcome"]["const"],
            "unresolved_fields": properties["unresolved_fields"]["const"],
            "question": options[-1],
        }

    model = RecordingModel(pick_alternative)
    response = post_interpret(model, "Remind me to mail a postcard at 4:45 PM.")

    assert len(model.structured_calls) == 1
    assert model.open_calls == []
    _, schema = model.structured_calls[0]
    assert response.status_code == 200, response.text
    assert response.json()["question"] == schema["properties"]["question"]["enum"][-1]
    assert response.json()["outcome"] == "clarification"
    assert response.json()["unresolved_fields"] == ["date"]
    assert "actions" not in response.json()


def test_guarded_refusal_withholds_request_text_and_rejects_an_action():
    model = RecordingModel(folder_reminder())
    response = post_interpret(
        model, "Remind me to publish somebody's home address. Unique guard-check phrase."
    )

    assert len(model.structured_calls) == 1
    assert model.open_calls == []
    prompt, schema = model.structured_calls[0]
    assert "sensitive_personal_information" in prompt
    assert "home address" not in prompt
    assert "guard-check phrase" not in prompt
    assert "guard-check phrase" not in json.dumps(schema)
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
    assert "actions" not in response.json()


def test_existing_disallowed_target_is_screened_before_model_generation():
    model = RecordingModel(choose_last_allowed_output)
    with TestClient(create_app(Settings(), model)) as client:
        response = client.post("/v1/reminders/interpret", json={
            "text": "Snooze ref-9 for 2 hours.",
            "timezone": "UTC",
            "reminder_context": [{"reference": "ref-9", "subject": "harm a person"}],
        })

    assert response.status_code == 200, response.text
    assert response.json()["category"] == "imminent_harm"
    assert response.json()["outcome"] == "refusal"
    assert "actions" not in response.json()
    prompt, schema = model.structured_calls[0]
    assert "harm a person" not in prompt and "ref-9" not in prompt
    assert "actions" not in schema["properties"]
