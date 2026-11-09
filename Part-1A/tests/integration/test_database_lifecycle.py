from unittest.mock import Mock

from fastapi.testclient import TestClient

import app.main as main
from app.database import DatabaseManager


def test_application_shutdown_closes_database_connection(tmp_path, monkeypatch) -> None:
    """FR-014, NFR-007: application shutdown releases its SQLite connection."""
    manager = DatabaseManager(database_path=str(tmp_path / "shutdown.db"))
    manager.initialize()
    close = Mock(wraps=manager.close)
    monkeypatch.setattr(main, "database_manager", manager)
    monkeypatch.setattr(manager, "close", close)

    try:
        with TestClient(main.app):
            pass
        close.assert_called_once_with()
    finally:
        manager.close()
