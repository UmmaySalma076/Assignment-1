from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.database import DatabaseManager


class TaskRepository:
    def __init__(
        self,
        database_manager: DatabaseManager,
        id_generator: Callable[[], int] | None = None,
    ) -> None:
        self.database_manager = database_manager
        self.id_generator = id_generator

    def create_task(
        self,
        title: str,
        description: str | None,
        completed: bool = False,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        timestamp = created_at or self._current_timestamp()
        with self.database_manager.get_connection() as connection:
            if self.id_generator is None:
                cursor = connection.execute(
                    """
                    INSERT INTO tasks (title, description, completed, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (title, description, int(completed), timestamp),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO tasks (id, title, description, completed, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.id_generator(), title, description, int(completed), timestamp),
                )
            task_id = cursor.lastrowid
            return self.get_task(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.database_manager.get_connection() as connection:
            rows = connection.execute(
                "SELECT id, title, description, completed, created_at FROM tasks ORDER BY id ASC"
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self.database_manager.get_connection() as connection:
            row = connection.execute(
                "SELECT id, title, description, completed, created_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            return self._row_to_task(row) if row is not None else None

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        completed: bool | None = None,
    ) -> dict[str, Any] | None:
        current = self.get_task(task_id)
        if current is None:
            return None

        next_title = title if title is not None else current["title"]
        next_description = description if description is not None else current["description"]
        next_completed = completed if completed is not None else current["completed"]

        with self.database_manager.get_connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, completed = ?
                WHERE id = ?
                """,
                (next_title, next_description, int(next_completed), task_id),
            )
            connection.commit()

        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self.database_manager.get_connection() as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _current_timestamp() -> str:
        from datetime import UTC, datetime

        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _row_to_task(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
        }
