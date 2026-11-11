from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.config import Settings
from reminder_agent.services.ollama import ModelReply


class UnusedModel:
    async def generate(self, _prompt):
        raise AssertionError("OpenAPI and rejected requests must not call Ollama")


def test_fastapi_openapi_documents_discriminated_outcomes_and_request_limit():
    client = TestClient(create_app(Settings(), UnusedModel()))
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/v1/reminders/interpret"]["post"]
    body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    components = schema["components"]["schemas"]
    request_model = components[body_schema["$ref"].split("/")[-1]]
    assert request_model["properties"]["text"]["maxLength"] == 2000
    assert operation["responses"]["400"]
    assert operation["responses"]["502"]
    assert operation["responses"]["503"]
    assert operation["responses"]["504"]
    assert "422" not in operation["responses"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert len(response_schema["oneOf"]) == 3
    assert response_schema["discriminator"]["propertyName"] == "outcome"
    client.close()


def test_implemented_api_matches_authored_openapi_contract():
    contract_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "specs"
        / "001-reminder-agent"
        / "contracts"
        / "openapi.yaml"
    )
    contract = contract_path.read_text(encoding="utf-8")
    client = TestClient(create_app(Settings(), UnusedModel()))
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/v1/reminders/interpret"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert "/v1/reminders/interpret:" in contract
    assert "maxLength: 2000" in contract
    assert "INVALID_REQUEST" in contract
    assert "OLLAMA_UNAVAILABLE" in contract
    assert len(response_schema["oneOf"]) == 3
    assert set(("400", "500", "502", "503", "504")).issubset(operation["responses"])
    client.close()


def test_configured_request_limit_rejects_before_model_submission():
    model = UnusedModel()
    client = TestClient(create_app(Settings(max_request_chars=3), model))
    response = client.post("/v1/reminders/interpret", json={"text": "four"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    client.close()


def test_request_length_counts_unicode_codepoints_and_accepts_hard_ceiling():
    model = UnusedModel()
    client = TestClient(create_app(Settings(max_request_chars=3), model))
    response = client.post("/v1/reminders/interpret", json={"text": "éééé"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    client.close()

    class ClarifyingModel:
        async def generate(self, prompt):
            return ModelReply(
                '{"outcome":"clarification","question":"What date, time and timezone should I use?",'
                '"unresolved_fields":["date","time","timezone"]}',
                "tinyllama:1.1b-chat-v0.6-q4_0",
                None,
                {},
                prompt,
            )

    client = TestClient(create_app(Settings(max_request_chars=2000), ClarifyingModel()))
    response = client.post("/v1/reminders/interpret", json={"text": "x" * 2000})
    assert response.status_code == 200
    assert response.json()["outcome"] == "clarification"
    client.close()


def test_invalid_json_contract_uses_stable_400_envelope():
    client = TestClient(create_app(Settings(), UnusedModel()))
    response = client.post("/v1/reminders/interpret", json={"text": "   ", "extra": True})
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    client.close()


def test_health_endpoints_do_not_generate_model_output():
    model = UnusedModel()
    client = TestClient(create_app(Settings(), model))
    assert client.get("/health/live").json() == {"status": "alive"}
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "OLLAMA_UNAVAILABLE"
    client.close()
