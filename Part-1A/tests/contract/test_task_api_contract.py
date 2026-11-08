import json
import logging

from fastapi.testclient import TestClient

from app.logging import StructuredFormatter


def test_task_requests_emit_structured_logs(client: TestClient) -> None:
    """NFR-004: API request and task events are emitted as structured logs."""
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    route_logger = logging.getLogger("app.api.routes")
    app_logger = logging.getLogger("app.main")
    handler = CaptureHandler()
    route_logger.addHandler(handler)
    app_logger.addHandler(handler)
    try:
        client.post("/tasks", json={"title": "Observable task"})
        client.get("/tasks")
    finally:
        route_logger.removeHandler(handler)
        app_logger.removeHandler(handler)

    events = {getattr(record, "event", None) for record in records}
    assert "task.created" in events
    assert "tasks.listed" in events
    assert "http.request.completed" in events
    request_record = next(
        record
        for record in records
        if record.event == "http.request.completed" and record.method == "GET"
    )
    structured = json.loads(StructuredFormatter().format(request_record))
    assert structured["method"] == "GET"
    assert structured["path"] == "/tasks"
    assert structured["status_code"] == 200


def test_list_tasks_contract_returns_empty_collection(client: TestClient) -> None:
    """FR-004, NFR-002, NFR-005: Empty listings have a stable successful response."""
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_create_task_contract(client: TestClient) -> None:
    """FR-001, FR-002, FR-003, FR-012, FR-013, NFR-002, NFR-005: Create contract."""
    response = client.post(
        "/tasks",
        json={"title": "Contract task", "description": "Example description"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"id", "title", "description", "completed", "created_at"}
    assert payload["completed"] is False
    assert payload["title"] == "Contract task"


def test_get_and_update_task_contract(client: TestClient) -> None:
    """FR-005, FR-006, FR-011, FR-012, NFR-002, NFR-005: Read and update contract."""
    create_response = client.post("/tasks", json={"title": "Original", "description": "Initial"})
    task_id = create_response.json()["id"]

    get_response = client.get(f"/tasks/{task_id}")
    put_response = client.put(
        f"/tasks/{task_id}",
        json={"title": "Replaced", "description": "New description", "completed": True},
    )
    patch_response = client.patch(f"/tasks/{task_id}", json={"title": "Patched"})

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Original"
    assert put_response.status_code == 200
    assert put_response.json()["title"] == "Replaced"
    assert put_response.json()["description"] == "New description"
    assert put_response.json()["completed"] is True
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Patched"
    assert patch_response.json()["completed"] is True


def test_validation_contract_rejects_invalid_task_data(client: TestClient) -> None:
    """FR-009, NFR-003, NFR-005: Invalid fields are rejected before mutation."""
    response = client.post("/tasks", json={"title": "", "description": "x" * 1001})
    assert response.status_code == 422


def test_validation_contract_rejects_non_boolean_status(client: TestClient) -> None:
    """FR-008, FR-009, NFR-003: Status input must be a boolean."""
    create_response = client.post("/tasks", json={"title": "Status validation"})
    task_id = create_response.json()["id"]

    response = client.patch(f"/tasks/{task_id}/status", json={"completed": "false"})

    assert response.status_code == 422


def test_status_contract_returns_404_for_missing_task(client: TestClient) -> None:
    """FR-010, NFR-005: A missing task returns the documented not-found response."""
    response = client.patch("/tasks/99999/status", json={"completed": True})
    assert response.status_code == 404


def test_status_contract_sets_current_boolean_state(client: TestClient) -> None:
    """FR-008, FR-011, NFR-002, NFR-005: Status setting updates current state."""
    created = client.post("/tasks", json={"title": "Status contract"})
    task_id = created.json()["id"]

    response = client.patch(f"/tasks/{task_id}/status", json={"completed": True})

    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_task_contract_accepts_maximum_field_lengths(client: TestClient) -> None:
    """FR-009, FR-012, NFR-003: Maximum title and description lengths are accepted."""
    response = client.post("/tasks", json={"title": "t" * 100, "description": "d" * 1000})

    assert response.status_code == 201
    assert len(response.json()["title"]) == 100
    assert len(response.json()["description"]) == 1000


def test_delete_contract_returns_204(client: TestClient) -> None:
    """FR-007, FR-010, NFR-005: Delete has a no-content response."""
    create_response = client.post("/tasks", json={"title": "Delete contract"})
    task_id = create_response.json()["id"]
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204
    assert response.text == ""
