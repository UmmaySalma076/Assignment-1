from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_task_service
from app.schemas.task import TaskCreate, TaskResponse, TaskStatusUpdate, TaskUpdate
from app.services.task_service import TaskNotFoundError, TaskService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task: TaskCreate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, Any]:
    try:
        created = service.create_task(task.title, task.description)
        logger.info(
            "Task created",
            extra={"event": "task.created", "task_id": created["id"]},
        )
        return created
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(service: Annotated[TaskService, Depends(get_task_service)]) -> list[dict[str, Any]]:
    tasks = service.list_tasks()
    logger.info(
        "Tasks listed",
        extra={"event": "tasks.listed", "task_count": len(tasks)},
    )
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, service: Annotated[TaskService, Depends(get_task_service)]) -> dict[str, Any]:
    try:
        return service.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def replace_task(
    task_id: int,
    payload: TaskUpdate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, Any]:
    try:
        return service.update_task(
            task_id,
            title=payload.title,
            description=payload.description,
            completed=payload.completed,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, Any]:
    try:
        return service.update_task(
            task_id,
            title=payload.title,
            description=payload.description,
            completed=payload.completed,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, Any]:
    try:
        return service.set_status(task_id, payload.completed)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> None:
    try:
        service.delete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
