import sqlite3
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.database import DatabaseManager
from app.repositories.task_repository import TaskRepository


def test_create_list_and_get_task(client: TestClient) -> None:
    """FR-001, FR-002, FR-003, FR-004, FR-005, FR-012, FR-013, NFR-002: Lifecycle."""
    response = client.post(
        "/tasks",
        json={"title": "Write tests", "description": "Draft the lifecycle checks"},
    )
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


def test_list_tasks_uses_ascending_id_order(client: TestClient) -> None:
    """FR-004, FR-013, NFR-002: List order is deterministic."""
    first = client.post("/tasks", json={"title": "First"})
    second = client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [
        first.json()["id"],
        second.json()["id"],
    ]


def test_update_task_preserves_unmodified_fields(client: TestClient) -> None:
    """FR-006, FR-011, FR-012, NFR-002: PATCH preserves omitted fields."""
    create_response = client.post(
        "/tasks",
        json={"title": "Original title", "description": "Original description"},
    )
    task_id = create_response.json()["id"]

    update_response = client.patch(f"/tasks/{task_id}", json={"title": "Updated title"})
    get_response = client.get(f"/tasks/{task_id}")

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated title"
    assert update_response.json()["description"] == "Original description"
    assert get_response.json()["title"] == "Updated title"


def test_update_task_status_is_idempotent(client: TestClient) -> None:
    """FR-008, FR-011, NFR-002: Repeated status-setting preserves current state."""
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


def test_create_uses_controlled_generated_id_and_timestamp(
    db_manager, monkeypatch
) -> None:
    """FR-002, FR-003, FR-013, NFR-002: Runtime values are controlled in tests."""
    expected_timestamp = "2026-11-09T12:34:56Z"
    repository = TaskRepository(db_manager, id_generator=lambda: 73)
    monkeypatch.setattr(repository, "_current_timestamp", lambda: expected_timestamp)

    task = repository.create_task("Deterministic task", None)

    assert task["id"] == 73
    assert task["created_at"] == expected_timestamp


def test_repository_rejects_duplicate_generated_ids(db_manager) -> None:
    """FR-002, FR-009: Duplicate task identifiers cannot create another task."""
    repository = TaskRepository(db_manager, id_generator=lambda: 19)
    repository.create_task("First", None)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_task("Duplicate", None)

    tasks = repository.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "First"


def test_sqlite_persists_tasks_across_manager_restart(tmp_path) -> None:
    """FR-002, FR-003, FR-012, FR-014, NFR-007: SQLite data survives restart."""
    database_path = tmp_path / "persistent-tasks.db"
    manager = DatabaseManager(database_path=str(database_path))
    manager.initialize()
    created = manager.task_service.create_task("Persistent task")
    manager.close()

    restarted_manager = DatabaseManager(database_path=str(database_path))
    restarted_manager.initialize()
    retrieved = restarted_manager.task_service.get_task(created["id"])

    assert retrieved["title"] == "Persistent task"
    assert retrieved["id"] == created["id"]
    restarted_manager.close()


def test_invalid_requests_do_not_mutate_tasks(client: TestClient) -> None:
    """FR-009, NFR-003: Invalid requests do not mutate persisted data."""
    created = client.post("/tasks", json={"title": "Keep valid"})
    task_id = created.json()["id"]

    invalid_create = client.post("/tasks", json={"title": " "})
    invalid_update = client.patch(f"/tasks/{task_id}", json={"title": "x" * 101})
    invalid_status = client.patch(f"/tasks/{task_id}/status", json={"completed": "done"})
    stored = client.get(f"/tasks/{task_id}").json()

    assert invalid_create.status_code == 422
    assert invalid_update.status_code == 422
    assert invalid_status.status_code == 422
    assert stored["title"] == "Keep valid"
    assert stored["completed"] is False


def test_delete_and_missing_task_errors(client: TestClient) -> None:
    """FR-007, FR-010, NFR-005: Delete and missing-task responses are consistent."""
    create_response = client.post("/tasks", json={"title": "Delete me"})
    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204

    fetch_after_delete = client.get(f"/tasks/{task_id}")
    assert fetch_after_delete.status_code == 404

    missing_delete = client.delete(f"/tasks/{task_id}")
    assert missing_delete.status_code == 404


def test_list_1000_tasks_within_response_time(client: TestClient, db_manager) -> None:
    """FR-004, NFR-001: GET /tasks returns 1,000 tasks in under 500 ms."""
    rows = [
        (f"Task {index}", "", 0, "2026-11-09T00:00:00Z")
        for index in range(1000)
    ]
    with db_manager.get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tasks (title, description, completed, created_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()

    start = time.perf_counter()
    response = client.get("/tasks")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert len(response.json()) == 1000
    assert elapsed < 0.5


def test_required_runtime_and_test_stack() -> None:
    """NFR-006: The project runs on Python 3.13 with FastAPI, Pydantic, and pytest."""
    import fastapi
    import pydantic
    import pytest

    assert sys.version_info[:2] == (3, 13)
    assert fastapi.__version__
    assert pydantic.__version__
    assert pytest.__version__
