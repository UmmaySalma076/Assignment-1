from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import DatabaseManager
from app.main import app


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "tasks.db"


@pytest.fixture
def db_manager(temp_db_path: Path) -> DatabaseManager:
    manager = DatabaseManager(database_path=str(temp_db_path))
    manager.initialize()
    try:
        yield manager
    finally:
        manager.close()


@pytest.fixture
def client(db_manager: DatabaseManager) -> TestClient:
    app.dependency_overrides = {}
    from app.api.deps import get_task_service

    def override_get_task_service():
        return db_manager.task_service

    app.dependency_overrides[get_task_service] = override_get_task_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
