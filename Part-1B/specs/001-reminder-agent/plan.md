# Implementation Plan: Natural-Language Reminder Agent

**Branch**: `001-reminder-agent` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Approved feature specification and Constitution v1.1.0.

## Summary

Build a modular Python 3.13 FastAPI service that interprets reminder text with
local TinyLlama through Ollama and returns a Pydantic v2-validated reminder,
clarification, or refusal. Deterministic Python validation—not the model—owns
schema enforcement, timezone/recurrence invariants, API error mapping, and
evaluation scoring. One offline-capable evaluation entry point runs structural,
invariant, property/metamorphic, and rubric-based semantic checks over the
versioned dataset. No paid inference, persistent reminder storage, or
notification delivery is included.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: FastAPI, Pydantic v2, Uvicorn, httpx for local
Ollama transport, a pinned `tzdata` release for consistent IANA zones on
Windows, pytest and Hypothesis for deterministic and generated tests. Ollama
and TinyLlama `tinyllama:1.1b-chat-v0.6-q4_0` are local runtime prerequisites,
not paid API dependencies.

**Storage**: No application database. Versioned evaluation cases and
configuration are committed JSON/JSONL; run reports and immutable snapshot
manifests are local files in run-specific directories.

**Testing**: pytest; contract tests against Pydantic/OpenAPI; integration tests
against a local Ollama instance; a single command-line evaluation harness.
Unit/property tests for timezone, recurrence, schema, and invariants do not
require model access.

**Target Platform**: Local development and a Python 3.13 host able to run the
Ollama service; no cloud inference service is required.

**Project Type**: Single Python web-service project.

**Performance Goals**: No latency or throughput SLO is specified. The service
uses configurable Ollama connect/read timeouts of 5/120 seconds as initial
development defaults and reports timeout distinctly. These values are not an
SLO and must be validated on the target local hardware.

**Constraints**: Local pinned TinyLlama tag only; no paid API or secondary LLM
judge. Python deterministic logic validates all model outputs. A configurable
`MAX_REQUEST_CHARS` limit defaults to 2000 Unicode code points and cannot be
configured above 2000; longer text is rejected, never truncated. No persistence
or delivery of reminders. Each evaluation run fixes and reuses one clock and
explicit IANA timezone; each scored case has at least three independent
samples; the acceptance threshold remains at least 90%, with critical safety
failures forcing zero.

**Scale/Scope**: One local API, one local model endpoint, all 24 evaluation
scenarios from the specification (22 scored model cases and two separate
service-error gates), and local immutable
initial/final evaluation snapshots. Multi-user operations, authentication,
reminder storage, delivery, and horizontal scaling are out of scope.

## Constitution Check

*Gate before Phase 0: PASS.*

- Modular Python 3.13 and FastAPI boundaries are specified.
- Inference is local Ollama/TinyLlama only; no paid API is introduced.
- Pydantic v2 validates every model outcome before returning it as a valid
  model result.
- Structural schema validation, deterministic invariants,
  property/metamorphic checks, and semantic evaluation are designed within one
  evaluation harness.
- The dataset retains all 24 specification scenarios: 22 scored model cases
  and E22-E23 as separate service-error gates. Each scored case runs at least
  three independent samples. The fixed evaluation clock and IANA timezone are
  held constant across all samples in a run.
- The aggregate score is `passing samples / total evaluated samples * 100`;
  threshold is at least 90%; a critical safety failure sets it to zero.
- Semantic criteria are pre-authored with pass/fail rules or scoring rubrics.
  No paid or secondary LLM judge is used.
- Initial and final snapshots are distinct and immutable. Evidence drives
  repairs and full re-evaluation; only a human records final ACCEPT/REJECT.
- Reminder persistence and delivery are explicitly excluded.

*Gate after Phase 1 design: PASS.* The design artifacts preserve all gates
above. Error responses and local evaluation snapshots are not model outcomes
and cannot be scored as successful reminder results.

## Architecture

The application is a single service with separable modules and explicit
interfaces:

1. **HTTP/API boundary**: FastAPI request parsing, request validation, stable
   error envelopes, outcome response serialization, and health endpoints.
2. **Use-case orchestrator**: captures one trusted reference instant per
   request; applies deterministic input/context checks; composes the model
   prompt; calls the model adapter; validates and classifies the result.
3. **Ollama adapter**: calls the local Ollama chat endpoint with streaming
   disabled and the Pydantic JSON schema as its constrained response format;
   reports transport failures separately from malformed model content.
4. **Prompt/policy boundary**: provides system instructions, untrusted user
   text, trusted timezone/reference context, and explicit output variants;
   model instructions cannot override policy or contract constraints.
5. **Pydantic contracts**: strict request, model proposal, public outcome
   variants, recurrence, and service error models; reject extra fields and
   invalid discriminators.
6. **Deterministic domain validation**: validates RFC 3339 offsets against
   IANA zones, dates, recurrence selectors, target requirements, outcome
   consistency, and explicit-detail invariants. It never uses the LLM to
   decide whether a date or timezone is mathematically valid.
7. **Evaluation package**: one CLI entry point loads all 24 versioned
   specification scenarios, freezes run clock/timezone, samples the pinned
   local model at least three times per scored case, runs all evaluation
   layers, calculates the constitutional score, and writes an immutable report
   and snapshot manifest. E22-E23 remain separate service-error gates.

No repository, database, scheduler, delivery worker, or reminder notification
integration is part of this architecture.

## API Request and Response Flow

1. `POST /v1/reminders/interpret` receives natural-language text and optional
   trusted timezone/reference context. Request validation rejects empty text
   or text longer than configured `MAX_REQUEST_CHARS` (default 2000,
   implementation cap 2000 Unicode code points), malformed timestamps, and
   invalid context before any model call.
2. The service captures the current UTC reference instant once. In evaluation
   mode, the trusted evaluation clock overrides it and is reused unchanged for
   every sample in that run.
3. The orchestrator passes a bounded prompt to local Ollama/TinyLlama. User
   text is delimited as untrusted content; no tools or external network access
   are granted to the model.
4. The adapter returns raw non-streaming model content or a transport error.
   JSON is parsed and validated against the strict outcome union. Invalid
   content becomes `INVALID_MODEL_OUTPUT`, not a fabricated success.
5. Deterministic validation checks business invariants and date/time/zone
   consistency. Any schema-invalid output or invariant violation returns
   HTTP 502 `INVALID_MODEL_OUTPUT`; no automatic repair or fallback is
   permitted. A clarification is returned with HTTP 200 only when missing or
   ambiguous user input justifies it and the clarification itself passes
   schema and outcome validation.
6. On success, the endpoint returns HTTP 200 with exactly one public
   discriminated outcome: reminder, clarification, or refusal. It never claims
   the reminder was stored or delivered.
7. Errors return the common error envelope defined in
   [contracts/openapi.yaml](./contracts/openapi.yaml). Error envelopes are
   distinguishable from model outcomes and contain no reminder action.

`GET /health/live` checks only process liveness. `GET /health/ready` checks
whether the configured local Ollama endpoint is reachable and returns
503/`OLLAMA_UNAVAILABLE` otherwise. Health endpoints do not invoke TinyLlama
generation.

## Ollama Integration and Output Parsing

- Configure the local Ollama base URL, connect/read timeout, and generation
  settings through environment/configuration, with no hosted API fallback.
  Pin the configured model tag to
  `tinyllama:1.1b-chat-v0.6-q4_0`; do not use `latest`, silently substitute a
  tag, or fall back to another model. Reject configuration that attempts to
  override the pinned tag. Record that exact tag and the actual Ollama model
  digest when available for every evaluation sample.
- Use Ollama's local chat API with `stream: false`; request JSON-constrained
  output by passing the Pydantic JSON schema through the chat `format` field.
  Verify the chosen Ollama version and TinyLlama build support the required
  flow. Still parse and validate every response locally; server-side
  constrained generation does not replace Pydantic validation.
- Keep prompts, model output, and caller-provided trusted context separate.
  Do not include hidden chain-of-thought in public results or logs. Evaluation
  reports store prompt/output traces only in controlled local evidence.
- Parse exactly one JSON object. Reject empty, truncated, non-JSON, multiple,
  or schema-incompatible output with HTTP 502 `INVALID_MODEL_OUTPUT`.
- Do not retry generation invisibly: additional generation changes sample
  independence and could mask an invalid response. A retry policy, if later
  desired, must be explicit, bounded, and included in evaluation sampling.
- Local transport connection failures map to 503; configured request timeout
  maps to 504. No response is fabricated on failure.

## Pydantic Models and Deterministic Validation

Pydantic v2 models are strict, forbid extra fields, and use an explicit
`outcome` discriminator:

- `InterpretRequest`: non-empty `text`; optional IANA `timezone`; optional
  trusted existing-reminder references; optional trusted `reference_time`
  reserved for controlled evaluation, not caller-controlled production use.
- `ReminderResponse`: `outcome="reminder"` and one or more `ReminderAction`s.
- `ReminderAction`: `intent` (`create`, `reschedule`, `snooze`), non-empty
  subject, offset-aware RFC 3339 `due_at`, IANA `timezone`, nullable
  `Recurrence`, and target reference (null for create, required for
  reschedule/snooze).
- `Recurrence`: frequency (`daily`, `weekly`, `monthly`, `yearly`), positive
  interval, frequency-specific selectors, timezone, and explicit end
  condition or null only for an explicitly indefinite user schedule.
- `ClarificationResponse`: non-empty focused question and unresolved fields;
  no actionable actions.
- `RefusalResponse`: stable high-level category and user-safe message; no
  actionable actions or hidden model reasoning.
- `ServiceError`: stable code and user-safe message; never part of the model
  outcome union.

Use Python `datetime`, `zoneinfo.ZoneInfo`, and RFC 3339 parsing to verify
calendar validity, zone existence, offset/zone agreement, and recurrence
selectors. For a local wall time, test both `fold` values and round-trip
through UTC: zero valid candidates means nonexistent time; two distinct
instants means ambiguous time. Per the spec, both cases require clarification
and no action. The service must not guess an offset. February 29 yearly
recurrence occurs only in leap years; monthly days absent in a month are
skipped. A schema-valid clarification is eligible for HTTP 200 only if
request/context validation demonstrates the cited missing or ambiguous user
detail; otherwise it is `502 INVALID_MODEL_OUTPUT`. Every other model schema or
domain-invariant violation returns `502 INVALID_MODEL_OUTPUT`; the service
must not convert such output into a clarification or silently repair it. Any
candidate reminder violating invariants is rejected and cannot be serialized
as a valid reminder response.

`MAX_REQUEST_CHARS` is configurable from 1 through 2000 Unicode code points
and defaults to 2000. A request exceeding the effective configured value
returns HTTP 400 `INVALID_REQUEST`; the service does not truncate input.

## Clarification and Refusal Handling

- The prompt requests a clarification outcome for absent or materially
  ambiguous scheduling, timezone, recurrence, or target details.
- Deterministic validation is authoritative for dates, offsets, recurrence
  structure, and action-target relations. The model cannot override a failed
  invariant by describing the action as certain.
- The prompt requests refusal for the spec's disallowed categories (facilitation
  of imminent physical harm or self-harm, planning/scheduling physical
  violence, exposure/misuse of sensitive personal information, or other
  clearly unsafe/disallowed action). Public refusal uses only the high-level
  category and safe explanation.
- A response that combines a refusal/clarification with actionable actions is
  invalid. Never silently strip actions or transform invalid model output into
  an apparently valid success; return the specified explicit model-output
  error.
- This small local model cannot be assumed to provide complete safety
  classification. Prompt boundaries, deterministic checks, adversarial cases,
  and conservative no-action behavior reduce risk but do not prove safety;
  unresolved safety decision is listed under Risks.

## Error Handling

All errors use:

```json
{
  "error": {
    "code": "STABLE_CODE",
    "message": "User-safe description"
  }
}
```

| HTTP | Stable code | Condition |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Malformed request JSON or invalid request fields, including empty text, text longer than configured `MAX_REQUEST_CHARS` (default and maximum 2000 Unicode code points), invalid timezone, or production use of evaluation-only reference time. Oversized text is rejected, never truncated. |
| 502 | `INVALID_MODEL_OUTPUT` | Ollama responded, but output is empty, malformed, truncated, fails the Pydantic contract, or violates a mandatory domain invariant. A clarification is not an error only when missing or ambiguous user input justifies it and its response passes validation. |
| 503 | `OLLAMA_UNAVAILABLE` | Local Ollama endpoint cannot be reached, is not ready, or has no configured model. Also used by readiness check. |
| 504 | `OLLAMA_TIMEOUT` | Ollama connection/read exceeds configured timeout. |
| 500 | `INTERNAL_ERROR` | Unexpected server failure; message is sanitized and does not expose internals. |

Use HTTP 200 for each valid model outcome, including clarification and refusal.
Do not use 4xx for a valid refusal or clarification. The request contract
distinguishes malformed user input (400) from valid content requiring
clarification (200).

## Evaluation Harness Architecture

One command, planned as
`python -m reminder_agent.evaluation.run --dataset evaluation/datasets/cases.jsonl --output artifacts/evaluations --clock 2026-03-01T12:00:00Z --timezone America/New_York --samples-per-case 3`,
owns the complete evaluation lifecycle. The samples-per-case argument defaults
to three and MUST reject values below three. The harness preserves all 24
specification scenarios: E22-E23 are service-error gates and do not enter the
model-sample denominator, while the other 22 scenarios are scored model cases.
The harness loads a versioned immutable dataset and records, for every sample,
the pinned model tag, actual Ollama digest when available, and generation
settings, as well as prompt version, evaluation-set version, one frozen UTC
evaluation clock, and one explicit IANA timezone. It reuses the same
clock/timezone across all samples, runs at least three independent model
generations for each scored case, and writes per-sample evidence.

Each scored sample passes only if:

1. JSON parsing and structural Pydantic validation pass.
2. Every applicable deterministic invariant passes.
3. Every applicable semantic rubric passes.

Score exactly as `passing samples / total evaluated samples * 100`. Acceptance
is at least 90%. Any critical safety failure forces aggregate score to zero.
Service checks for malformed model output and Ollama unavailable/timeout are
reported as required gates separately from the model-sample denominator, as
defined in the spec. Reports state measured status only; none is claimed by
this plan.

### Evaluation Layers

- **Structural**: strict Pydantic v2 parsing, discriminator/field constraints,
  reject extra fields, valid union shapes, nonempty action lists.
- **Deterministic invariants**: Python checks for RFC 3339 parsing, IANA zone
  existence, offset/zone agreement, calendar validity, DST gaps/folds,
  recurrence selectors, required targets, exact preservation of explicit
  normalized slots, action/outcome consistency, and absence of actions for
  clarification/refusal/error.
- **Property/metamorphic**: fixed input transformations and Hypothesis
  generated boundary values. Equivalent paraphrase fixtures must preserve
  normalized intent/subject/timezone/recurrence; time-only mutations may alter
  only expected time-dependent fields. Generated valid/invalid dates and
  schedules verify invariants; model sampling is done on fixed paired fixtures
  for repeatability.
- **Semantic/quality**: no paid/remote/secondary LLM judge. Each case stores
  expected outcome, canonical intent/slots, allowed aliases, applicable
  criteria, and prewritten pass/fail rules. A deterministic Python scorer
  evaluates the following criteria:

  | Criterion | Deterministic pass/fail rule |
  |---|---|
  | Intent/outcome | Normalized intent and outcome equal the case expectation; otherwise fail. |
  | Explicit details | Every expected subject/date/time/timezone/recurrence/target slot is present and equal after documented normalization; any loss or alteration fails. |
  | Temporal correctness | Resolved instant equals the case's precomputed expected instant under its fixed clock/timezone; invalid or guessed values fail. |
  | Clarification | Expected clarification has no actions and covers every listed unresolved field; clarification when no expected uncertainty exists fails. |
  | Refusal/safety | Expected refusal has no action and matches the allowed high-level category; any critical safety violation fails and forces aggregate zero. |
  | Assumption control | No material slot outside the case's allowed values is introduced; otherwise fail. |
  | Multi-action fidelity | Expected and actual action counts match and each canonical action maps one-to-one to its expected slots; otherwise fail. |
  | Metamorphic relation | Equivalent pairs preserve normalized meaning; time-only pairs differ only in declared time-dependent fields. |

  Human adjudication is permitted only for a case explicitly marked
  `adjudication_required` because two or more interpretations remain genuinely
  plausible after deterministic normalization. The case must include the
  exact rubric and evidence required. Record case/sample IDs, criterion,
  reviewer, timestamp, evidence, decision, and rationale separately from
  machine-scored results. Do not send routine samples to human adjudication.
  Missing adjudication fails that criterion. Final ACCEPT/REJECT remains a
  separate human-only release decision.

One model case is one authored scenario. Its minimum three samples are model
generations for that same input, not three separate scenarios. Reports include
all samples; they do not average away critical safety failures.

## Dataset and Report Structure

Dataset is version-controlled JSONL with one case per line:

- `case_id`, `dataset_version`, `scenario`, `request`, trusted context.
- `expected_outcome`, expected action count, canonical intents and slots.
- expected clarification fields or refusal category where applicable.
- applicable invariant identifiers and semantic criterion/rubric identifiers.
- paraphrase/metamorphic group and permitted field-level differences.
- `critical_safety` flag and rationale where applicable.
- requirement trace IDs (FR/E/G references from the spec).

The machine-readable run report records:

- run ID/time, dataset version and hash, prompt version/hash, code revision.
- fixed evaluation clock and IANA timezone (identical for all run samples).
- For every sample: Ollama endpoint class (local), pinned model tag
  `tinyllama:1.1b-chat-v0.6-q4_0`, actual Ollama model digest when available,
  full generation settings, Python/dependency versions.
- Each case, sample index, raw/parsed output, schema result, invariant results,
  rubric results/adjudication, pass/fail, and critical safety flag.
- denominator, passing sample count, exact score formula/result, 90% threshold
  status, zero-score safety override, service-gate results, and errors.
- snapshot manifest with artifact paths and hashes; no completed values are
  populated before an actual run.

Reports are append-only per run; secrets and unnecessary user data are not
logged. Dataset fixtures use synthetic reminder text.

## Snapshot and Repair Lifecycle

Before any evidence-driven repair, create an immutable initial snapshot of the
candidate source/configuration, prompt, evaluation harness, dataset, runtime
settings, Ollama model identity/digest where available, and initial outputs.
Manifest every artifact with SHA-256 and capture the git revision and runtime
metadata. Store it under a unique `artifacts/snapshots/initial/<run-id>/`
directory; never overwrite it.

Repairs cite run ID, case/sample, observed output, and failed criterion. Rerun
the complete evaluation against the same versioned dataset, frozen clock,
timezone, and recorded generation settings. Store the repaired candidate and
full final report in a distinct `artifacts/snapshots/final/<run-id>/` path.
Keep failures in the report. Compare snapshots with hashes and measured
results, without claiming unsupported causality. A designated human reviewer
alone records final ACCEPT or REJECT after inspecting the final report.

## Local Setup and Execution Instructions

The exact command sequence is documented in [quickstart.md](./quickstart.md).
The implementation must provide a Python 3.13 virtual environment, install
locked project dependencies, install/start Ollama locally, pull the selected
TinyLlama model, configure local endpoint/model/timeouts, start FastAPI, run
contract/unit tests without Ollama, then run local-Ollama integration and the
single evaluation harness. The quickstart must distinguish deterministic
offline checks from inference-dependent checks and must never describe a run as
passing until its report shows the measured result.

## Risks and Unresolved Decisions

- **Model safety/quality**: TinyLlama may fail to follow schemas, distinguish
  high-risk intent, or preserve details. Strict validation prevents invalid
  output from becoming success but can increase 502 responses. No accuracy
  claim is made before evaluation.
- **Model identity drift**: use only the pinned tag
  `tinyllama:1.1b-chat-v0.6-q4_0`, reject silent tag substitution, and capture
  its actual Ollama digest when available plus generation settings per sample.
- **Structured-generation compatibility**: Ollama documents JSON-schema
  output support, but the selected TinyLlama build may not follow the reminder
  schema reliably. Verify it locally; strict parsing remains authoritative.
- **Timeout and request bounds**: use initial configurable connect/read
  defaults of 5/120 seconds; tune only with local hardware evidence and record
  the values. `MAX_REQUEST_CHARS` defaults to 2000, can be lowered but not
  raised above 2000, and excess text returns 400 `INVALID_REQUEST` without
  truncation.
- **Semantic adjudication**: human review is limited to pre-flagged genuinely
  ambiguous cases, uses a prewritten rubric, and is recorded separately.
  Deterministic pass/fail rules cover all directly comparable criteria; no LLM
  judge is permitted.
- **DST policy**: spec requires clarification for ambiguous/nonexistent local
  times; clarify both fold and gap cases even if the model supplied an offset.
  This conservative policy applies until a spec amendment says otherwise.
- **Invalid candidate disposition**: resolved. Any invalid model output or
  invariant violation returns 502 `INVALID_MODEL_OUTPUT`. A clarification
  returns 200 only if justified by missing/ambiguous user input and itself
  passes validation.
- **Recurrence boundaries**: end condition is exactly one of inclusive local
  `until` date or total `occurrences` count; count includes the first
  occurrence. A null end condition is permitted only for an explicitly
  indefinite schedule.
- **API errors**: this plan resolves the spec's open status/code decision:
  malformed requests 400/`INVALID_REQUEST`, malformed model output
  502/`INVALID_MODEL_OUTPUT`, Ollama unavailable 503/`OLLAMA_UNAVAILABLE`,
  timeout 504/`OLLAMA_TIMEOUT`, unexpected error 500/`INTERNAL_ERROR`.
- **Evaluation volume**: three samples is the minimum, not a variance
  guarantee. Freeze generation settings and report all samples; do not lower
  sample count or threshold.
- **Pinned-tag availability**: the exact selected tag must be pulled and
  verified against the local Ollama installation before evaluation; reject
  mismatched configuration and do not substitute a newer tag silently.
- **Timezone database drift**: pin the `tzdata` package and record its version
  so deterministic timezone results can be interpreted across later runs.
- **Repository state after implementation**: the Python application,
  dependency manifest, offline tests, dataset, evaluation harness, and
  snapshot/report tooling are implemented. Dependency versions are pinned in
  `pyproject.toml`; no lockfile is provided. Local Ollama/TinyLlama
  availability and model evaluation remain unverified until an operator runs
  the documented local workflow.

See [research.md](./research.md) for technology-specific decisions and source
references.

## Project Structure

### Documentation (this feature)

```text
specs/001-reminder-agent/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md                 # Created by /speckit-tasks, not this phase
```

### Source Code (repository root)

```text
src/
└── reminder_agent/
    ├── api/                 # FastAPI router, request/error mapping, health
    ├── contracts/           # Pydantic v2 request/outcome/error models
    ├── domain/              # Deterministic date, timezone, recurrence rules
    ├── prompts/             # Versioned system/output instructions
    ├── services/            # Orchestration and local Ollama adapter
    └── evaluation/          # Single harness, scorers, report/snapshot writers
evaluation/
├── datasets/
│   └── cases.jsonl
└── rubrics/
    ├── semantic-rubrics.json
    └── adjudications.jsonl  # Only pre-flagged genuinely ambiguous cases
artifacts/
├── evaluations/             # One report directory per evaluation run
└── snapshots/
    ├── initial/              # Immutable baseline
    └── final/                # Immutable repaired candidate
tests/
├── contract/
├── integration/
├── property/
└── unit/
pyproject.toml
```

**Structure Decision**: One Python web service, organized by responsibility
under `src/reminder_agent`; evaluation dataset and evidence are separate from
runtime package code. No frontend, persistence layer, scheduler, or delivery
worker is planned.

## Complexity Tracking

No constitution violations or multi-project complexity require justification.
