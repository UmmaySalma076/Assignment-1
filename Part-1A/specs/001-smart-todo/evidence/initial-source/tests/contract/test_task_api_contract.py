from fastapi.testclient import TestClient


def test_create_task_contract(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "Contract task", "description": "Example description"})
    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"id", "title", "description", "completed", "created_at"}
    assert payload["completed"] is False
    assert payload["title"] == "Contract task"


def test_validation_contract_rejects_invalid_task_data(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "", "description": "x" * 1001})
    assert response.status_code == 422


def test_status_contract_returns_404_for_missing_task(client: TestClient) -> None:
    response = client.patch("/tasks/99999/status", json={"completed": True})
    assert response.status_code == 404


def test_delete_contract_returns_204(client: TestClient) -> None:
    create_response = client.post("/tasks", json={"title": "Delete contract"})
    task_id = create_response.json()["id"]
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204
    assert response.text == ""
