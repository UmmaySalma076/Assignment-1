---
description: "Implementation tasks for the Natural-Language Reminder Agent"
---

# Tasks: Natural-Language Reminder Agent

**Input**: Design documents from `specs/001-reminder-agent/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/openapi.yaml`

**Tests**: Test tasks are included for the contract, deterministic rules, API journeys, property/metamorphic checks, and evaluation harness because these checks are required by the specification and plan. No test or evaluation results are implied by this task list.

**Organization**: Tasks are grouped by the three user stories in `spec.md`. Shared runtime and API foundations precede the stories; evaluation and release-evidence work follows them.

**Implementation paths**: Paths below are relative to the Part-1B project root.

## Phase 1: Setup

**Purpose**: Establish the Python project and planned package structure.

- [X] T001 [P] Create `pyproject.toml` for Python 3.13 with FastAPI, Pydantic v2, Uvicorn, httpx, pinned tzdata, pytest, and Hypothesis dependencies; configure the `src/` package layout and pytest discovery.
- [X] T002 [P] Create `__init__.py` files at `src/reminder_agent/__init__.py`, `src/reminder_agent/api/__init__.py`, `src/reminder_agent/contracts/__init__.py`, `src/reminder_agent/domain/__init__.py`, `src/reminder_agent/prompts/__init__.py`, `src/reminder_agent/services/__init__.py`, and `src/reminder_agent/evaluation/__init__.py`.

## Phase 2: Foundational

**Purpose**: Build shared configuration, contracts, model access, and API boundaries required by all stories.

- [X] T003 [P] Implement validated runtime settings in `src/reminder_agent/config.py`, including the pinned `tinyllama:1.1b-chat-v0.6-q4_0` model tag, local Ollama endpoint, configurable 5/120-second initial connect/read timeouts, and FR-024 `MAX_REQUEST_CHARS` default 2000 constrained to 1–2000 Unicode code points.
- [X] T004 [P] Implement strict Pydantic v2 request, reminder, recurrence, clarification, refusal, and service-error contracts in `src/reminder_agent/contracts/models.py`; enforce non-empty request text, FR-024 effective request-size rejection using HTTP 400 `INVALID_REQUEST` without truncation or model submission, supported intents and outcomes, required fields, forbidden extra fields, and a recurrence end condition with exactly one of inclusive `until` or positive `occurrences`.
- [X] T005 Implement the local Ollama adapter in `src/reminder_agent/services/ollama.py`; call `/api/chat` with streaming disabled and the Pydantic JSON schema, use only the configured local TinyLlama tag, and expose raw response content, configured tag, available model digest, and effective generation settings without remote fallback.
- [X] T006 Create the versioned system/output instructions in `src/reminder_agent/prompts/reminder_system.txt`; delimit user text as untrusted, constrain outputs to the documented outcome contract, and prohibit claims of persistence or delivery.
- [X] T007 Implement the FastAPI application and routes in `src/reminder_agent/api/app.py` and stable error mapping in `src/reminder_agent/api/errors.py`; return 400 `INVALID_REQUEST`, 502 `INVALID_MODEL_OUTPUT`, 503 `OLLAMA_UNAVAILABLE`, 504 `OLLAMA_TIMEOUT`, or 500 `INTERNAL_ERROR` as specified, and implement `/health/live` and `/health/ready`.
- [X] T008 Add configuration, contract, and OpenAPI compatibility tests in `tests/unit/test_config.py` and `tests/contract/test_openapi.py`, verifying FR-024 `MAX_REQUEST_CHARS` defaults to 2000, accepts configuration only from 1 through 2000, rejects longer request text without truncation or model submission using HTTP 400 `INVALID_REQUEST`, and verifying discriminated outcome variants, recurrence selector exclusivity, and stable API error envelope/status mappings.

## Phase 3: User Story 1 - Create a Reminder (Priority: P1) — MVP

**Goal**: Interpret one or more create requests as faithful, validated actions with deterministic date, time, timezone, and recurrence handling.

**Independent Test**: With a stubbed local-model adapter, submit clear one-time and recurring create requests; verify the returned action details, normalized time and timezone, recurrence rules, and absence of any claim that a reminder was stored or delivered.

### Tests for User Story 1

- [X] T009 [P] [US1] Add deterministic temporal and recurrence boundary tests in `tests/unit/test_time_validation.py` and `tests/unit/test_recurrence.py` for valid RFC 3339 values, IANA-zone offset agreement, DST gaps/folds, recurrence selector exclusivity, skipped monthly dates, and leap-year February 29 behavior.
- [X] T010 [P] [US1] Add create-flow API journey tests in `tests/integration/test_create_interpretation.py` for explicit and relative dates, multiple reminders, preservation of explicit subjects/details, and a fixed reference clock/timezone using a stubbed Ollama adapter.

### Implementation for User Story 1

- [X] T011 [US1] Implement deterministic RFC 3339, IANA timezone, offset agreement, DST gap/fold, and reference-clock validation in `src/reminder_agent/domain/time.py`; nonexistent or ambiguous local times must not produce an actionable result.
- [X] T012 [US1] Implement recurrence validation in `src/reminder_agent/domain/recurrence.py`; support daily, weekly, monthly, and yearly schedules, required frequency selectors, skipped unavailable monthly dates, leap-year-only February 29 dates, and an inclusive `until` date OR positive total `occurrences` count, never both.
- [X] T013 [US1] Implement create-action interpretation and invariant validation in `src/reminder_agent/services/interpreter.py`; preserve distinct actions and explicit user slots, use the trusted or captured reference clock and timezone, and reject unsupported assumptions or invalid model output.
- [X] T014 [US1] Connect create interpretation to `POST /v1/reminders/interpret` in `src/reminder_agent/api/app.py` and satisfy the create journey checks in `tests/integration/test_create_interpretation.py` without adding reminder persistence or notification delivery.

## Phase 4: User Story 2 - Reschedule or Snooze (Priority: P2)

**Goal**: Interpret reschedule and snooze requests only when their target is unique and the requested replacement time or duration is valid.

**Independent Test**: With one unique trusted reminder reference, verify a reschedule action and a one-time snooze action; with a missing or non-unique target, verify a clarification with no actions.

### Tests for User Story 2

- [X] T015 [P] [US2] Add reschedule and snooze API journey tests in `tests/integration/test_reschedule_snooze.py` for unique, missing, and non-unique targets, explicit replacement times, snooze durations, and no mutation of trusted reminder context.

### Implementation for User Story 2

- [X] T016 [US2] Implement target resolution in `src/reminder_agent/domain/targets.py`; reschedule and snooze require exactly one matching trusted reminder reference and must clarify rather than guess when the target is missing or non-unique.
- [X] T017 [US2] Extend `src/reminder_agent/services/interpreter.py` for reschedule and snooze actions; preserve the unique target, require a deterministically resolved replacement time or snooze interval, require snooze recurrence to be null, and return no success-shaped fallback for invalid output.
- [X] T018 [US2] Connect reschedule and snooze outcomes to `POST /v1/reminders/interpret` in `src/reminder_agent/api/app.py` and satisfy `tests/integration/test_reschedule_snooze.py` without looking up or changing persisted reminders.

## Phase 5: User Story 3 - Resolve Uncertainty and Handle Unsafe Requests (Priority: P3)

**Goal**: Return validated, focused clarifications for missing or materially ambiguous details and safe refusals for the specified disallowed requests, with no actionable content in either outcome.

**Independent Test**: Submit missing/ambiguous, conflicting, and disallowed requests through the API with a stubbed model; verify a justified clarification or refusal, no actions, and rejection of unjustified or structurally invalid model outcomes.

### Tests for User Story 3

- [X] T019 [P] [US3] Add clarification and safety API journey tests in `tests/integration/test_clarification_safety.py` for missing details, ambiguous dates/timezones, conflicting instructions, disallowed categories, prompt-override attempts, and no-action outcomes.

### Implementation for User Story 3

- [X] T020 [US3] Implement clarification validation in `src/reminder_agent/domain/clarification.py`; require a focused question and unresolved field/conflict, justify clarification from request or trusted context, and reject clarification outcomes containing actions.
- [X] T021 [US3] Implement refusal validation in `src/reminder_agent/domain/safety.py` and update `src/reminder_agent/prompts/reminder_system.txt` for the specification's disallowed categories; require a stable high-level category and safe message, with no actions or hidden policy/reasoning.
- [X] T022 [US3] Integrate clarification/refusal checks into `src/reminder_agent/services/interpreter.py` and verify `tests/integration/test_clarification_safety.py`; return HTTP 200 only for justified, fully validated outcomes and HTTP 502 `INVALID_MODEL_OUTPUT` for schema or invariant violations.

## Phase 6: Evaluation, Evidence, and Cross-Cutting Concerns

**Purpose**: Implement the one evaluation harness, preserve evidence and snapshots, and document local execution and human-only release review.

- [ ] T023 [P] Create `evaluation/datasets/cases.jsonl` with all 24 specification scenarios E01–E24, expected outcomes and canonical slots, fixed-context expectations, applicable invariants and semantic criteria, and requirement trace IDs; score E01–E21 and E24 with at least three samples per case and retain E22–E23 as separate service-error gates.
- [X] T024 [P] Create `evaluation/rubrics/semantic-rubrics.json` with deterministic pass/fail rules for every mechanically assessable semantic criterion before candidate evaluation; define the record shape for pre-flagged genuinely ambiguous cases and separately recorded adjudications in `evaluation/rubrics/adjudications.jsonl`.
- [X] T025 Add evaluation unit tests in `tests/unit/test_evaluation.py` for the exact score formula `passing samples / total evaluated samples * 100`, the unchanged 90% threshold, the three-sample minimum, fixed clock/timezone reuse, sample denominator rules, and zero score on any critical safety failure.
- [X] T026 [P] Implement strict structural and deterministic invariant scorers in `src/reminder_agent/evaluation/structural.py` and `src/reminder_agent/evaluation/invariants.py`; cover schema conformance, date/time/zone consistency, explicit-detail preservation, action-target consistency, and no-action outcomes.
- [X] T027 [P] Implement rubric-based semantic scoring and narrowly scoped adjudication recording in `src/reminder_agent/evaluation/semantic.py`; assess intent, explicit details, temporal correctness, clarification/refusal, assumption control, and multi-action fidelity without any LLM judge or paid API.
- [X] T028 [P] Implement property/metamorphic evaluation in `src/reminder_agent/evaluation/metamorphic.py` and generated boundary tests in `tests/property/test_reminder_properties.py`; verify equivalent paraphrases preserve normalized meaning, time-only changes do not alter unrelated fields, and generated valid/invalid temporal and recurrence inputs satisfy invariants.
- [X] T029 Implement the single evaluation entry point in `src/reminder_agent/evaluation/run.py`; load the versioned dataset, reject fewer than three samples per scored case, fix and reuse one evaluation clock and explicit IANA timezone for every sample, run all evaluation layers, and report E22–E23 as separate service gates.
- [X] T030 Implement per-sample provenance and machine-readable report writing in `src/reminder_agent/evaluation/reports.py`; record prompts, dataset/version/hash, code revision, configured model tag, actual Ollama digest when available, generation settings, runtime versions, outputs, criterion results, denominator, score, threshold status, safety override, service gates, and errors.
- [X] T031 Implement non-overwriting initial and final snapshot manifests in `src/reminder_agent/evaluation/snapshots.py`; preserve candidate/configuration/harness/dataset and reports under distinct `artifacts/snapshots/initial/<run-id>/` and `artifacts/snapshots/final/<run-id>/` paths, and reject attempts to replace an existing snapshot.
- [X] T032 Add separate service-error gate tests in `tests/integration/test_service_error_gates.py` for malformed/schema-invalid/invariant-invalid model output (502 `INVALID_MODEL_OUTPUT`), Ollama unavailability (503 `OLLAMA_UNAVAILABLE`), timeout (504 `OLLAMA_TIMEOUT`), and absence of fabricated successful outcomes.
- [X] T033 Update `specs/001-reminder-agent/quickstart.md` with the implemented Python 3.13 setup, local Ollama/TinyLlama configuration, API commands, test commands, evaluation CLI, and expected error/gate behavior; document FR-024 `MAX_REQUEST_CHARS` default 2000, allowed range 1–2000, and HTTP 400 `INVALID_REQUEST` without truncation or model submission.
- [X] T034 Document evidence-based repair and human-only release review in `specs/001-reminder-agent/quickstart.md`; require repairs to cite observed failing cases/criteria, full re-evaluation after repair, preservation of distinct initial/final snapshots, and an explicit human-recorded ACCEPT or REJECT without an automated release decision.

**Checkpoint**: All user stories and evaluation infrastructure are implemented; this is not evidence that tests or model evaluation have passed.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 and T002 are independent and may run in parallel.
- **Foundational (Phase 2)**: Depends on Setup. T003 and T004 may run in parallel; the Ollama adapter, prompt, API, and contract checks depend on their required shared configuration/contracts.
- **User Story 1 (Phase 3)**: Depends on the Foundation. The temporal/recurrence tests can be authored in parallel; their implementations precede create-flow integration.
- **User Story 2 (Phase 4)**: Depends on User Story 1 because it extends the shared interpretation service and API flow.
- **User Story 3 (Phase 5)**: Depends on User Story 1 and User Story 2 because its policy validation must guard the complete interpretation flow.
- **Evaluation and Polish (Phase 6)**: Dataset and rubric authorship may proceed in parallel after the story requirements are understood. Scorers and property checks depend on those authored expectations; the runner depends on the scorers, reports, and dataset. Snapshot and final quickstart work depend on the evaluation/report lifecycle.

### User Story Dependencies

- **US1 (P1)**: Starts after the Foundation; no dependency on another user story. This is the MVP.
- **US2 (P2)**: Starts after US1 because it extends the shared interpreter and API endpoint.
- **US3 (P3)**: Starts after US1 and US2 so clarification/refusal enforcement covers the complete action set.

### Parallel Opportunities

- T001 and T002 can run in parallel.
- T003 and T004 can run in parallel after setup.
- T009 and T010 can run in parallel; they cover separate test files.
- T023 and T024 can run in parallel; they produce separate dataset and rubric files.
- T026, T027, and T028 can be developed in parallel after their required evaluation expectations exist.
- User stories are intentionally ordered where they extend the shared interpreter/API rather than marking conflicting edits as parallel.

## Independent Test Criteria

- **US1**: A stubbed-model API request with an explicit one-time schedule returns a validated create action with the same subject, date/time, and IANA timezone; a complete recurrence satisfies deterministic recurrence rules. Multiple requested reminders remain distinct. Invalid or uncertain dates never yield an action.
- **US2**: A unique trusted target yields the requested reschedule or one-time snooze action; absent or ambiguous targets yield a no-action clarification. The trusted context is not mutated.
- **US3**: Missing or materially ambiguous details yield a justified, focused no-action clarification; disallowed requests yield a validated no-action refusal; invalid model outcomes return 502 rather than being rewritten as successful outcomes.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundation.
2. Complete User Story 1 and independently verify its API journey using a stubbed local-model adapter.
3. Stop at the US1 checkpoint if an MVP is needed before implementing reschedule/snooze, safety/clarification, and full evaluation.

### Incremental Delivery

1. Add US2 after the create flow to support target-based reschedule and snooze.
2. Add US3 to enforce clarification and refusal behavior across the interpretation flow.
3. Build the versioned 24-scenario dataset and one complete evaluation harness.
4. Preserve an initial snapshot before evidence-based repairs; after repair, run the full harness and preserve a separate final snapshot. Only a human records ACCEPT or REJECT.

## Completion Notes

- Request-length behavior is specified by FR-024, tested through conformance gate G06, and traced to T003, T004, T008, and T033.
- No evaluation or test result is asserted by these tasks.
- T023 remains unchecked: the 24-case dataset and three-sample scoring guard are implemented and tested, but live model scoring was deliberately not run. No model evaluation report or initial/final model-run snapshot was generated.
