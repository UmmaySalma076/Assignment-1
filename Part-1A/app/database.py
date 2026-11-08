import sqlite3
from pathlib import Path

from app.config import settings


class DatabaseManager:
    def __init__(self, database_path: str | None = None) -> None:
        path = Path(database_path) if database_path is not None else Path(settings.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = str(path)
        self._connection: sqlite3.Connection | None = None
        self.repository = None
        self.task_service = None

    def get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def initialize(self) -> None:
        with self.get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        if self.repository is None:
            from app.repositories.task_repository import TaskRepository

            self.repository = TaskRepository(self)
        if self.task_service is None:
            from app.services.task_service import TaskService

            self.task_service = TaskService(self.repository)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


database_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager:
    return database_manager
