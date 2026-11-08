# Task API Contract

## Overview

This contract defines the public HTTP interface for the Smart Todo Application. It is intentionally aligned with the specification and the clarified decisions: validation failures return `422`, delete returns `204`, and task completion is represented by the current state only.

## Common conventions

- Content type: `application/json`
- All task responses use a consistent JSON shape.
- Task IDs are integer values.
- Timestamps are ISO 8601 strings.
- Task order in list responses is ascending `id`.

## Task object

```json
{
  "id": 1,
  "title": "Buy groceries",
  "description": "Milk, bread, and eggs",
  "completed": false,
  "created_at": "2026-11-09T00:00:00Z"
}
```

## Endpoint: POST /tasks

**Purpose**: Create a task.

**Request body**

```json
{
  "title": "Buy groceries",
  "description": "Milk, bread, and eggs"
}
```

**Success response**

- Status: `201 Created`
- Body: `Task`

**Validation failure**

- Status: `422 Unprocessable Entity`
- Body: FastAPI/Pydantic validation error payload

## Endpoint: GET /tasks

**Purpose**: List all tasks.

**Success response**

- Status: `200 OK`
- Body:

```json
[
  {
    "id": 1,
    "title": "Buy groceries",
    "description": "Milk, bread, and eggs",
    "completed": false,
    "created_at": "2026-11-09T00:00:00Z"
  }
]
```

## Endpoint: GET /tasks/{task_id}

**Purpose**: Fetch a single task by ID.

**Success response**

- Status: `200 OK`
- Body: `Task`

**Not found**

- Status: `404 Not Found`

## Endpoint: PUT /tasks/{task_id}

**Purpose**: Replace a task record with a valid full-task payload.

**Success response**

- Status: `200 OK`
- Body: `Task`

**Validation failure**

- Status: `422 Unprocessable Entity`

**Not found**

- Status: `404 Not Found`

## Endpoint: PATCH /tasks/{task_id}

**Purpose**: Update one or more task fields.

**Success response**

- Status: `200 OK`
- Body: `Task`

**Validation failure**

- Status: `422 Unprocessable Entity`

**Not found**

- Status: `404 Not Found`

## Endpoint: PATCH /tasks/{task_id}/status

**Purpose**: Set the current completion status.

**Behavior**: This operation is idempotent. Repeating the same status value must leave the task in the same state and must not create completion-history records. For example, sending `{"completed": true}` repeatedly when the task is already completed must return the same completed state without persisting extra history.

**Request body**

```json
{
  "completed": true
}
```

**Success response**

- Status: `200 OK`
- Body: `Task`

**Validation failure**

- Status: `422 Unprocessable Entity`

**Not found**

- Status: `404 Not Found`

## Endpoint: DELETE /tasks/{task_id}

**Purpose**: Delete a task.

**Success response**

- Status: `204 No Content`
- Body: none

**Not found**

- Status: `404 Not Found`
