# Tasks: Smart Todo Application

**Input**: Design documents from `/specs/001-smart-todo/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the Python 3.13 FastAPI project and shared tooling for deterministic, testable task execution.

- [X] T001 Create project structure per implementation plan in `app/`, `tests/`, `specs/001-smart-todo/`
- [X] T002 Initialize Python 3.13 project metadata and dependency manifest for FastAPI, Pydantic, SQLite, pytest, Ruff, and Bandit
- [X] T003 [P] Configure Ruff and Bandit in project configuration to validate linting and security checks
- [X] T004 [P] Create shared application bootstrap and configuration module in `app/config.py` and `app/main.py`
- [X] T005 [P] Create `tests/conftest.py` with isolated SQLite fixture and deterministic test setup, including freezing or mocking runtime-generated IDs and timestamps for exact-value assertions in FR-013 and NFR-002 without making production identifiers or timestamps static

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the database layer, validation contract, and base API behavior before any story-specific work.

**Critical**: No user story work can begin until this phase is complete.

- [X] T006 Create SQLite database initialization and connection management in `app/database.py` for FR-014 and NFR-007
- [X] T007 Implement `tasks` table schema in `app/database.py` with fields `id`, `title`, `description`, `completed`, and `created_at` matching the data model and FR-012
- [X] T008 [P] Implement repository layer stub and CRUD interface in `app/repositories/task_repository.py` for FR-002, FR-005, FR-006, FR-007, FR-008, FR-010, and FR-014
- [X] T009 [P] Create shared validation helpers in `app/utils/validation.py` enforcing title length <= 100 and description length <= 1000 (FR-009, FR-012, Input Validation Rules)
- [X] T010 [P] Define Pydantic request/response schemas in `app/schemas/task.py` for create, update, status, and task response models using 422 validation behavior and consistent task payload fields (FR-001, FR-006, FR-008, FR-009, FR-012, API Contracts)
- [X] T011 Create service layer skeleton in `app/services/task_service.py` that orchestrates validation, repository calls, and deterministic ordering logic (FR-004, FR-013, NFR-002)
- [X] T012 Configure structured logging and error handling in `app/logging.py` and `app/api/deps.py` to ensure secure error responses without leaking internals (FR-009, NFR-005, Constitution: Input validation and secure error handling)
- [X] T013 Create a minimal harness evidence capture file or runner for test execution and command output in `tests/fixtures/` or `scripts/` to document pass/fail evidence for the feature (Requirement: harness development and evidence capture)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Create and list tasks (Priority: P1) 🎯 MVP

**Goal**: Allow users to create a valid task and retrieve the current task list with deterministic ordering and metadata.

**Independent Test**: A valid task can be created, listed, and verified to include the required fields with stable ordering and correct status.

### Tests for User Story 1

- [X] T014 [P] [US1] Contract test for `POST /tasks` and `GET /tasks` in `tests/contract/test_task_api_contract.py` (FR-001, FR-003, FR-004, FR-012, API Contracts, 201/200/422)
- [X] T015 [P] [US1] Integration test for task creation and listing in `tests/integration/test_task_lifecycle.py` (FR-001, FR-003, FR-004, FR-012, FR-013)

### Implementation for User Story 1

- [X] T016 [P] [US1] Implement task creation repository behavior in `app/repositories/task_repository.py` to insert a task and generate a valid unique identifier and timestamp (FR-002, FR-003, FR-012)
- [X] T017 [P] [US1] Implement task listing repository behavior in `app/repositories/task_repository.py` with deterministic ascending-id ordering (FR-004, FR-013)
- [X] T018 [US1] Implement service logic for create and list in `app/services/task_service.py` with validation, timestamp generation, and error translation for invalid input (FR-001, FR-003, FR-009, FR-012, FR-013)
- [X] T019 [US1] Implement `POST /tasks` and `GET /tasks` endpoints in `app/api/routes.py` with correct status codes and JSON payloads (FR-001, FR-004, API Contracts)
- [X] T020 [US1] Add explicit validation and error handling for empty/invalid titles and overlong description values in `app/api/routes.py` and `app/utils/validation.py` (FR-009, Input Validation Rules, 422 handling)
- [X] T021 [US1] Add structured request and task-creation logs in `app/logging.py` for create/list operations (Constitution: Structured logging and observability)

**Checkpoint**: User Story 1 should be fully functional and independently testable.

---

## Phase 4: User Story 2 - Retrieve, update, and mark status (Priority: P1)

**Goal**: Allow users to fetch a single task by ID, update task details, and toggle the current completion state without requiring historical completion logs.

**Independent Test**: A task can be looked up by ID, modified, and marked completed or pending while preserving the current state and returning correct status codes.

### Tests for User Story 2

- [X] T022 [P] [US2] Contract test for `GET /tasks/{task_id}`, `PUT /tasks/{task_id}`, `PATCH /tasks/{task_id}`, and `PATCH /tasks/{task_id}/status` in `tests/contract/test_task_api_contract.py` (FR-005, FR-006, FR-008, FR-010, FR-011, FR-012, API Contracts)
- [X] T023 [P] [US2] Integration test for retrieving, updating, and toggling task status in `tests/integration/test_task_lifecycle.py`, including repeated status updates that remain idempotent without creating completion-history records (FR-005, FR-006, FR-008, FR-010, FR-011, FR-013)

### Implementation for User Story 2

- [X] T024 [P] [US2] Implement single-task fetch and update repository operations in `app/repositories/task_repository.py` for FR-005, FR-006, FR-010, FR-011 (current status only)
- [X] T025 [P] [US2] Implement status toggle service logic in `app/services/task_service.py` to set completed/pending without adding historical completion records (FR-008, FR-011)
- [X] T026 [US2] Implement `GET /tasks/{task_id}` and `PUT /tasks/{task_id}` endpoints in `app/api/routes.py` with 200 and 404 handling (FR-005, FR-006, FR-010, API Contracts)
- [X] T027 [US2] Implement `PATCH /tasks/{task_id}` and `PATCH /tasks/{task_id}/status` endpoints in `app/api/routes.py` with 200, 404, and 422 handling (FR-006, FR-008, FR-009, FR-011, API Contracts)
- [X] T028 [US2] Add validation rules for boolean status payloads, idempotent completion-state semantics, and task ID existence checks in `app/utils/validation.py` and `app/services/task_service.py` (FR-008, FR-009, FR-010, FR-011, Input Validation Rules)

**Checkpoint**: User Story 2 should be fully functional and independently testable.

---

## Phase 5: User Story 3 - Delete task and invalid-request handling (Priority: P2)

**Goal**: Ensure a task can be removed and all invalid or missing-task conditions return the defined error behavior without unsupported silent failures.

**Independent Test**: A task can be deleted, and both missing IDs and invalid payloads return the correct not-found and validation responses.

### Tests for User Story 3

- [X] T029 [P] [US3] Contract test for `DELETE /tasks/{task_id}` and validation error responses in `tests/contract/test_task_api_contract.py` (FR-007, FR-009, FR-010, API Contracts, DELETE=204, validation=422)
- [X] T030 [P] [US3] Integration test for deleting tasks and rejecting invalid requests in `tests/integration/test_task_lifecycle.py` (FR-007, FR-009, FR-010, NFR-005)
- [X] T031 [P] [US3] Unit test for validation boundaries in `tests/unit/test_task_validation.py` (title length <= 100, description length <= 1000, empty title rejections) (FR-009, Input Validation Rules)

### Implementation for User Story 3

- [X] T032 [US3] Implement repository delete operation in `app/repositories/task_repository.py` to remove a task and ensure subsequent fetches return not found (FR-007, FR-010)
- [X] T033 [US3] Implement delete endpoint in `app/api/routes.py` with `204 No Content` and not-found handling (FR-007, API Contracts)
- [X] T034 [US3] Add deterministic validation failures and error response mapping in `app/api/routes.py` and `app/services/task_service.py` to return 422 for invalid payloads and 404 for missing task IDs (FR-009, FR-010, Error Handling)
- [X] T035 [US3] Add edge-case guard clauses for empty task list, invalid status values, duplicate ID handling, and deleted-item retrieval in service logic and tests (Edge Cases, FR-010, FR-013)

**Checkpoint**: User Story 3 should be fully functional and independently testable.

---

## Phase 6: Final Validation and Cross-Cutting Concerns

**Purpose**: Enforce quality gates, security checks, evidence capture, and explicit human review for the complete feature.

- [X] T036 [P] Run syntax and lint validation across the project (for example, Python compilation/formatting checks plus Ruff) and fix any issues before final review (Constitution: Clean, modular, maintainable Python code; Tooling requirement: Ruff)
- [X] T037 [P] Run deterministic unit, integration, and contract tests for the full Smart Todo workflow in `tests/unit/`, `tests/integration/`, and `tests/contract/` using controlled IDs and timestamps for exact-value assertions (FR-001 through FR-014, SC-001 through SC-006, FR-013, NFR-002)
- [X] T038 [P] Run Bandit security scanning across `app/` and fix any reported issues before final approval (Constitution: secure error handling; Tooling requirement: Bandit)
- [X] T039 [P] Capture structured failure and feedback evidence for every execution result, including command output, pass/fail summaries, and the exact failing harness evidence, without inventing successful outcomes (Requirement: harness development and evidence capture)
- [X] T040 [P] Execute self-healing based on actual harness failure evidence, then re-run the affected checks to confirm the repair succeeded and record the before/after evidence (Requirement: self-healing using actual harness failure evidence)
- [X] T041 [P] Preserve the initial execution logs, repaired code state, and post-repair execution logs for auditability and review, including the relationship between failure evidence and final repair decisions (Requirement: evidence preservation)
- [X] T042 [P] Require explicit human ACCEPT or REJECT review of all harness results, test reports, security scans, repair evidence, and final validation output before declaring completion; record the decision and justification, and do not automatically approve the application (Constitution: final acceptance or rejection requires human review)
- [X] T043 Update `specs/001-smart-todo/quickstart.md` validation checklist to reflect the final verified commands and expected outcomes after test execution (NFR-004, documentation quality)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: No dependencies; begins immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user story work.
- **User Story 1 (Phase 3)**: Depends on Setup + Foundational.
- **User Story 2 (Phase 4)**: Depends on Setup + Foundational and can begin in parallel with US1 after the foundation is ready.
- **User Story 3 (Phase 5)**: Depends on Setup + Foundational and can be developed in parallel with US1/US2 after foundation is ready.
- **Final Validation (Phase 6)**: Depends on all story tasks and quality checks completing.

### Story dependencies

- **US1 (P1)**: No dependencies on other stories; it is the MVP baseline.
- **US2 (P1)**: Depends only on the shared foundation and can proceed in parallel with US1 once the foundation is ready.
- **US3 (P2)**: Depends only on the shared foundation and can proceed in parallel with US1/US2 once the foundation is ready.

### Parallel opportunities

- Setup tasks T003, T004, and T005 can run in parallel.
- Foundational tasks T008, T009, T010, and T013 can run in parallel when the base project structure exists.
- Story test tasks for each user story can run in parallel with their implementation tasks when the foundation is complete.
- The final validation tasks T036 through T043 can run in parallel once all feature implementation tasks are complete, with T040/T041/T042 executed against the same captured harness evidence and human review records.

---

## Implementation Strategy

### MVP first

1. Complete Setup and Foundational phases.
2. Deliver User Story 1 (create + list tasks) as the first working increment.
3. Validate the MVP with contract and integration tests.
4. Extend to User Story 2 (single-item read + update + status toggle).
5. Extend to User Story 3 (delete + validation and not-found handling).
6. Run final quality assurance and evidence capture before acceptance.

### Incremental delivery

- Each user story is independently testable and can be delivered as a discrete feature increment.
- The shared foundation is intentionally minimal but strong enough to support all stories without leaking implementation details into the specification.
- Cross-cutting quality gates (Ruff, Bandit, README validation, harness evidence) run at the end so they verify the entire feature rather than individual stories in isolation.

---

## Requirement Mapping

- FR-001, FR-003, FR-012, API Contracts: T007, T010, T014, T016, T018, T019
- FR-002, FR-005, FR-006, FR-007, FR-008, FR-010, FR-011, FR-014: T006, T008, T024, T025, T026, T027, T032, T033, T034
- FR-004, FR-013, NFR-002: T011, T017, T023, T035, T036
- FR-009, Input Validation Rules, Error Handling: T009, T010, T020, T028, T030, T031, T034
- NFR-005, NFR-007, Constitution observability/security requirements: T012, T037, T038
- SC-001 through SC-006 and all user stories: T014-T043

This task list preserves the specification, quality gates, and acceptance criteria without weakening the required implementation requirements.
