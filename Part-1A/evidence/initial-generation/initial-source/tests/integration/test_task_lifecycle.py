from fastapi.testclient import TestClient


def test_create_list_and_get_task(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "Write tests", "description": "Draft the lifecycle checks"})
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Write tests"
    assert created["completed"] is False
    assert created["description"] == "Draft the lifecycle checks"

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == created["id"]

    get_response = client.get(f"/tasks/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Write tests"


def test_update_task_status_is_idempotent(client: TestClient) -> None:
    create_response = client.post("/tasks", json={"title": "Review patch"})
    task_id = create_response.json()["id"]

    first_status = client.patch(f"/tasks/{task_id}/status", json={"completed": True})
    second_status = client.patch(f"/tasks/{task_id}/status", json={"completed": True})

    assert first_status.status_code == 200
    assert second_status.status_code == 200
    assert first_status.json()["completed"] is True
    assert second_status.json()["completed"] is True

    pending_response = client.patch(f"/tasks/{task_id}/status", json={"completed": False})
    assert pending_response.status_code == 200
    assert pending_response.json()["completed"] is False

    repeated_pending = client.patch(f"/tasks/{task_id}/status", json={"completed": False})
    assert repeated_pending.status_code == 200
    assert repeated_pending.json()["completed"] is False


def test_delete_and_missing_task_errors(client: TestClient) -> None:
    create_response = client.post("/tasks", json={"title": "Delete me"})
    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204

    fetch_after_delete = client.get(f"/tasks/{task_id}")
    assert fetch_after_delete.status_code == 404

    missing_delete = client.delete(f"/tasks/{task_id}")
    assert missing_delete.status_code == 404
