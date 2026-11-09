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
- Test tasks for different user stories may be prepared in parallel after the foundation is complete, but each test MUST be written and run before the corresponding implementation change begins, in accordance with the constitution's test-first requirement.
- T036-T043 are already-completed historical validation tasks and do not replace the required Harness v2 run. The new final phase T044-T051 must be completed strictly in sequence.
- The new Harness v2 and remediation phase (T044-T051) is strictly sequential; none of its tasks may run in parallel or start before the preceding task is complete.

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
- NFR-001: T046, T048 (1,000-task response-time test and revalidation)
- NFR-002: T005, T011, T015, T023, T035, T037, T046, T048
- NFR-003: T009, T010, T020, T028, T030, T031, T034, T046
- NFR-004: T012, T021, T043, T044, T045, T048, T050
- NFR-005, NFR-007, Constitution observability/security requirements: T006, T012, T037, T038, T044, T045, T048
- NFR-006: T002, T044, T046, T048
- SC-001 through SC-006 and all user stories: T014-T043
- SC-007: T046, T048

## Phase 7: Harness v2 and remediation

**Purpose**: Enforce constitution v1.1.0 quality gates, close requirement/test traceability gaps, validate the revised acceptance criteria, preserve reproducible evidence, and require a final human decision.

**Execution rule**: Complete T044 through T051 in order. Each task depends on the immediately preceding task; do not run these tasks in parallel. T051 is the Harness v2 human decision and must not be completed until T044-T050 are complete.

- [x] T044 Create `.harness/ruff.toml` under student/human control (the implementation agent MUST NOT modify this file) and create `.harness/run.py` to enforce the constitution v1.1.0 gates: run `ruff check . --config .harness/ruff.toml` and require exit 0 with zero violations; run `bandit -r app -ll` and require zero MEDIUM/HIGH issues; run all pytest tests with `app/` line coverage at least 85%; verify every active FR-xxx and NFR-xxx identifier appears in at least one test; and check constitution guardrails prohibiting `# noqa`/`# nosec`, weakened or skipped tests/acceptance criteria, lowered quality thresholds, edited recorded results, and committed secrets or `.env` files. The guardrails must freeze the reviewed test/spec/config baseline, detect tracked result edits, and inspect active `app/`, `tests/`, and `.harness/` sources. Do not modify the constitution. (Constitution v1.1.0; prerequisite for T045)
- [x] T045 Run `.harness/run.py` against the current implementation and save the complete initial report, exact commands and outputs, and pass/fail results under the repository-root `evidence/results/`. Preserve failures as observed; do not repair code during this task. (Depends on T044)
- [x] T046 Add all applicable FR-xxx and NFR-xxx identifiers to tests in `tests/contract/test_task_api_contract.py`, `tests/integration/test_task_lifecycle.py`, and `tests/unit/test_task_validation.py`; update contract tests for PUT replacement defaults (AC-005) and PATCH omitted-field retention (AC-006); add an integration test that proves SQLite task data survives an application/database-manager restart (AC-012 in the current spec; previously numbered AC-011); and add an integration performance test that prepares exactly 1,000 tasks before timing `GET /tasks`, asserts status 200, all 1,000 returned tasks, and response time under 500 ms (AC-016). Write and run each new acceptance-behavior test and capture its failing result against the current code before making any corresponding implementation change; preserve the observed failing output in repository-root `evidence/results/`. (Depends on T045; FR/NFR traceability, AC-005, AC-006, AC-012, AC-016, SC-007)
- [x] T047 Repair failures only when supported by the saved harness/test evidence in repository-root `evidence/results/`; make the smallest code changes necessary, preserve the original failure evidence, and record each evidence-to-repair relationship. Do not modify tests or acceptance criteria to make a failure pass. (Depends on T046)
- [x] T048 Re-run the exact same `.harness/run.py` harness and gates used in T045, without weakening or changing them, and save the complete repaired-run report, commands, outputs, and results under repository-root `evidence/results/`. (Depends on T047)
- [x] T049 Preserve the final validated source snapshot in repository-root `evidence/final-generation/`, with a provenance manifest linking it to the passing T048 report. (Depends on T048)
- [x] T050 Write `specs/001-smart-todo/evidence/harness-log.md` (done by the student), recording the ordered T044-T049 execution, exact evidence paths, test-first failures, evidence-based repairs, final harness results, and snapshot provenance. Do not invent results or record the human decision here. (Depends on T049)
- [ ] T051 After T044-T050 are complete, obtain and record a human ACCEPT or REJECT decision and the human's justification in repository-root `evidence/results/human-review-v2.json` (do not overwrite the earlier review). The decision must review the initial and final harness reports, test reports, security scan, failure/repair evidence, final snapshot, and harness log. The AI MUST NOT make or imply this decision. (Depends on T050; final gate)

### Acceptance Criterion to Test Task Mapping

| Acceptance criterion | Test task(s) |
|---|---|
| AC-001 | T014, T015 |
| AC-002 | T014, T015 |
| AC-003 | T014, T015, T035 |
| AC-004 | T022, T023 |
| AC-005 | T022, T023, T046 |
| AC-006 | T022, T023, T046 |
| AC-007 | T022, T023 |
| AC-008 | T022, T023 |
| AC-009 | T022, T023 |
| AC-010 | T022, T023 |
| AC-011 | T029, T030 |
| AC-012 | T046 |
| AC-013 | T029, T030, T031 |
| AC-014 | T029, T030 |
| AC-015 | T031 |
| AC-016 | T046, T048 |

This phase adds Harness v2 verification without changing or unchecking any previously completed task. Existing completed tasks and their recorded outcomes remain intact.

This task list preserves the specification, quality gates, and acceptance criteria without weakening the required implementation requirements.
