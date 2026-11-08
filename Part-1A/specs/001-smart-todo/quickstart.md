# Quickstart: Smart Todo Application

## Prerequisites

- Python 3.13
- FastAPI
- Pydantic
- SQLite support in the Python runtime
- pytest
- Ruff
- Bandit

## Local setup

Run these commands from the `Part-1A` project directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

The application initializes its SQLite database automatically. The default database file is `tasks.db` in the project directory.

## Validation scenarios

### Create a task

1. POST to `/tasks` with a valid payload containing a title and optional description.
2. Confirm status `201` and a response body containing the fields `id`, `title`, `description`, `completed`, and `created_at`.

### List tasks

1. GET `/tasks`.
2. Confirm the response status is `200` and the returned list is ordered deterministically by `id`.

### Fetch one task

1. GET `/tasks/{task_id}` using a known valid ID.
2. Confirm the returned task matches the stored values.
3. Confirm a missing ID returns `404`.

### Update a task

1. PUT or PATCH `/tasks/{task_id}` with valid task data.
2. Confirm the status is `200` and the updated values are returned.
3. Confirm invalid payloads return `422`.

### Toggle completion state

1. PATCH `/tasks/{task_id}/status` with `{"completed": true}` or `{"completed": false}`.
2. Confirm the task reflects the new completion state.

### Delete a task

1. DELETE `/tasks/{task_id}`.
2. Confirm the status is `204` and the task is no longer retrievable.
3. Confirm a missing ID returns `404`.

## Example test commands

```powershell
python -m compileall -q app tests
python -m ruff check .
python -m pytest -q
python -m bandit -r app
```

## Expected outcomes

- Syntax, lint, unit, integration, API contract, and security checks exit successfully.
- All task lifecycle operations work without violating the specification.
- Validation failures return `422`.
- Task deletion returns `204`.
- Current completion status is preserved without requiring completion history.
- Equivalent inputs produce consistent API behavior under the same persisted state.
- Tests that assert exact IDs or timestamps use controlled values; production IDs and timestamps remain runtime-generated.

To run the full validation harness and preserve a JSON report, combined log, and code snapshot under `specs/001-smart-todo/evidence/`, run:

```powershell
python scripts/run_harness.py --label final-validation
```

Review the captured outputs and security scan before making the required human `ACCEPT` or `REJECT` decision. The harness does not approve the application automatically.
