# Implementation Plan: Smart Todo Application

**Branch**: `001-smart-todo` | **Date**: 2026-11-09 | **Spec**: `specs/001-smart-todo/spec.md`

**Input**: Feature specification from `/specs/001-smart-todo/spec.md`

## Summary

The feature delivers a small, deterministic FastAPI-based task management service with SQLite-backed persistence. It supports task creation, list retrieval, single-task lookup, full or partial update, deletion, and completion toggling while enforcing the clarified requirements: title length <= 100, description length <= 1000, DELETE returns 204, validation failures return 422, and current completion state is tracked without historical completion logs. The planned implementation follows the constitution by maintaining deterministic API semantics, validating inputs early, testing with pytest, and documenting behavior through API contract checks and operational guidance.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: FastAPI, Pydantic, SQLite, pytest, Ruff, Bandit

**Storage**: Embedded SQLite database with a single tasks table and deterministic ordering strategy.

**Testing**: pytest for unit, integration, and API-contract tests; Ruff for linting; Bandit for static security analysis.

**Target Platform**: Linux/macOS/Windows development environment with FastAPI ASGI server.

**Project Type**: Web service / API application

**Performance Goals**: Support a small-to-moderate task dataset with low-latency CRUD operations under local development conditions.

**Constraints**: Deterministic behavior for equivalent requests; no historical completion log required; strict validation and stable status codes; no silent weakening of tests or requirements.

**Scale/Scope**: Single-user or single-tenant task service; limited to task lifecycle operations and local persistence.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The planned implementation conforms to the project constitution because it:

- preserves clean, modular Python structure and clear module boundaries,
- enforces deterministic API behavior under equivalent conditions,
- requires test-first pytest validation before acceptance,
- validates API contracts and integration flows,
- validates inputs and secures error responses,
- uses structured logging and observability as operational norms,
- keeps the design simple and aligned with the documented specification.

No constitution violations are identified for this feature. The clarified requirements are explicitly captured in the specification and are consistent with the governing principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-smart-todo/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── tasks-api.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md                  # phase 2 artifact not created by /speckit-plan
```

### Source Code (repository root)

```text
app/
├── __init__.py
├── main.py
├── config.py
├── database.py
├── models/
│   ├── __init__.py
│   └── task.py
├── repositories/
│   ├── __init__.py
│   └── task_repository.py
├── schemas/
│   ├── __init__.py
│   └── task.py
├── api/
│   ├── __init__.py
│   ├── deps.py
│   └── routes.py
├── services/
│   ├── __init__.py
│   └── task_service.py
├── utils/
│   ├── __init__.py
│   └── validation.py
└── logging.py

tests/
├── contract/
│   └── test_task_api_contract.py
├── integration/
│   └── test_task_lifecycle.py
├── unit/
│   └── test_task_validation.py
├── conftest.py
└── fixtures/
    └── test_db.sqlite3
```

**Structure Decision**: A single FastAPI application with modular subpackages for API routes, schemas, repository, service, and persistence logic. The selected layout keeps responsibilities isolated while remaining straightforward for a small task-oriented service.

## Architecture and Component Structure

1. Application entrypoint
   - `app/main.py` initializes the FastAPI application, configures the SQLite connection, and wires dependency injection.
   - The app exposes the task resource endpoints defined by the specification.

2. Configuration and database layer
   - `app/config.py` contains environment-driven configuration for database path, app metadata, and validation defaults.
   - `app/database.py` owns SQLite connection management and migration or initialization routines.

3. Domain model and schema layer
   - `app/models/task.py` defines the task entity at the domain level.
   - `app/schemas/task.py` defines Pydantic request and response models with field constraints matching the specification.
   - Validation is centralized so request payloads, update payloads, and response serialization align with one contract.

4. Persistence layer
   - `app/repositories/task_repository.py` contains all SQLite data access logic: create, list, fetch by ID, update, delete, and completion toggling.
   - The repository isolates the database implementation from service logic and keeps the API layer ceremony-light.

5. Service layer
   - `app/services/task_service.py` manages business logic, validation coordination, and deterministic ordering rules.
   - It ensures that task creation and updates preserve only the current completion state as required by the clarified spec.

6. API layer
   - `app/api/routes.py` defines the endpoints for task lifecycle operations.
   - It translates domain errors into consistent HTTP responses: 200, 201, 204, 404, and 422.
   - Deterministic responses and consistent ordering are enforced here and in the repository.

7. Shared validation and observability utilities
   - `app/utils/validation.py` handles length constraints and common validation rules.
   - `app/logging.py` configures structured logs for requests, repository actions, and API exceptions.

## Database Schema and Persistence Approach

The application uses an embedded SQLite database for a small, reliable, deterministic task store.

### Schema

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    description TEXT,
    completed INTEGER NOT NULL CHECK(completed IN (0, 1)),
    created_at TEXT NOT NULL
);
```

### Persistence rules

- Primary key is an integer identifier generated by SQLite, ensuring uniqueness and stable lookup by task ID.
- Title length is constrained to 1-100 characters after trimming whitespace.
- Description length is constrained to 0-1000 characters after trimming whitespace when provided.
- `completed` uses a boolean-compatible integer (`0` = pending, `1` = completed) to simplify SQLite interoperability.
- `created_at` is stored as ISO 8601 UTC text in a consistent format.
- Query ordering MUST be deterministic, such as ascending `id` or a documented stable ordering rule.
- Data remains local to the application instance and is durable across restarts within the chosen SQLite file.

### Deterministic design approach

- Identifiers are generated by SQLite rather than by a random algorithm, but the contract remains deterministic because sequence order and retrieval behavior are predictable.
- Runtime-generated timestamps are treated as a valid part of the system, while tests freeze or stub time where exact value assertions are required.
- Equivalent input sequences in a fixed database state produce equivalent observable outputs.

## API Implementation Approach

The FastAPI application will expose the task endpoints defined by the specification:

- `POST /tasks` to create a task
- `GET /tasks` to list tasks
- `GET /tasks/{task_id}` to fetch a single task
- `PUT /tasks/{task_id}` to replace task data
- `PATCH /tasks/{task_id}` to partially update
- `PATCH /tasks/{task_id}/status` to toggle completion state
- `DELETE /tasks/{task_id}` to remove a task

### Request and response model strategy

- Use Pydantic models for request validation and serialization.
- Separate models for create, update, status, and response payloads avoid accidental over-permissiveness.
- Each response includes the task identifier, title, description, completion state, and creation timestamp.

### Error and status handling

- Validation failures use `422 Unprocessable Entity` with structured error details.
- Missing resources use `404 Not Found`.
- Successful deletes return `204 No Content` with no response body.
- Successful create, update, and status toggles return `201` or `200` with the task payload as applicable.

### Deterministic API semantics

- Task ordering is fixed by repository query ordering.
- Response schema is consistent across equivalent requests.
- API surface and status codes are designed to support contract testing and stable acceptance criteria.

## Input Validation and Error Handling

The implementation will enforce all clarified rules at the boundary before storing data.

### Validation rules

- Title is required, trimmed, non-empty, and within 1-100 characters.
- Description is optional but, if provided, must be within 0-1000 characters.
- `completed` must resolve to a valid boolean-compatible value for the API and database.
- Task ID values must exist before update, delete, or lookup operations.
- Request body parsing must reject malformed JSON and invalid field types before persistence.

### Error handling approach

- Use FastAPI validation exceptions to return consistent 422 responses.
- Use repository or service-layer `NotFoundError` handling to translate missing tasks into 404 responses.
- Keep messages descriptive without exposing internal stack traces or sensitive implementation details.
- Avoid silent fallback; invalid operations fail clearly and deterministically.

## Testing Strategy

### Test-first compliance

The implementation must follow the constitution’s requirement to write failing tests before implementation. The test suite should include deterministic fixtures and explicit validation of edge cases.

### Test layers

1. Unit tests
   - Validate Pydantic constraining rules for title and description length.
   - Test repository query ordering and database update behavior.
   - Confirm service validation logic handles missing IDs and invalid transitions.

2. Integration tests
   - Validate end-to-end task lifecycle: create → list → fetch by ID → update → complete → delete.
   - Confirm 404 and 422 behaviors are consistent.
   - Validate state transitions from pending to completed and back.

3. API contract tests
   - Model HTTP payloads and status codes against the spec.
   - Verify JSON contract shape and exact response codes for create, list, fetch, update, delete, and status toggles.

4. Security/static checks
   - Run Ruff to enforce lint and import hygiene.
   - Run Bandit to catch common security issues in the application code.

### Deterministic testing rules

- Where exact values are asserted for timestamps or IDs, tests must freeze or patch generation so that behavior remains deterministic and not dependent on runtime variability.
- Database fixtures must use isolated SQLite temporary files to avoid cross-test contamination.
- Ordering assertions must compare sorted record sets rather than relying on environment-specific ordering patterns.

## Security Considerations

- Validate all incoming data to reject malformed or oversized inputs before persistence.
- Ensure no sensitive error details or stack traces are exposed through API responses.
- Use parameterized SQLite queries to avoid SQL injection risks in repository operations.
- Keep task data local and minimal; do not add external secrets or authentication requirements unless explicitly introduced by the requirements.
- Run Bandit in CI to flag common security issues in Python code.
- Keep logging structured and free of sensitive task contents, while capturing enough data for operational debugging.

## Project Directory Structure

```text
.
├── .specify/
│   ├── memory/
│   ├── scripts/
│   └── ...
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── logging.py
│   ├── api/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── unit/
│   ├── conftest.py
│   └── fixtures/
├── README.md
├── requirements.txt
├── pyproject.toml
├── .ruff.toml
├── .bandit
└── .gitignore
```

## Complexity Tracking

No constitution violations or complexity exceptions are required for this feature. The design remains intentionally small and aligns with the specification without introducing unneeded abstraction or multi-service complexity.
