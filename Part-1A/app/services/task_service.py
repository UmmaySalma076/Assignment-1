from __future__ import annotations

from typing import Any

from app.repositories.task_repository import TaskRepository
from app.utils.validation import validate_completed, validate_description, validate_title


class TaskNotFoundError(ValueError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task {task_id} was not found.")
        self.task_id = task_id


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def create_task(self, title: str, description: str | None = None) -> dict[str, Any]:
        clean_title = validate_title(title)
        clean_description = validate_description(description)
        return self.repository.create_task(
            title=clean_title,
            description=clean_description,
            completed=False,
        )

    def list_tasks(self) -> list[dict[str, Any]]:
        return self.repository.list_tasks()

    def get_task(self, task_id: int) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        completed: bool | None = None,
    ) -> dict[str, Any]:
        self.get_task(task_id)

        if title is not None:
            title = validate_title(title)
        if description is not None:
            description = "" if description == "" else validate_description(description)
        if completed is not None:
            completed = validate_completed(completed)

        updated = self.repository.update_task(
            task_id,
            title=title,
            description=description,
            completed=completed,
        )
        if updated is None:
            raise TaskNotFoundError(task_id)
        return updated

    def set_status(self, task_id: int, completed: bool | int) -> dict[str, Any]:
        clean_completed = validate_completed(completed)
        current = self.get_task(task_id)
        if current["completed"] == clean_completed:
            return current
        return self.update_task(task_id, completed=clean_completed)

    def delete_task(self, task_id: int) -> None:
        if not self.repository.get_task(task_id):
            raise TaskNotFoundError(task_id)
        deleted = self.repository.delete_task(task_id)
        if not deleted:
            raise TaskNotFoundError(task_id)
