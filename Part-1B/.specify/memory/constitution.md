<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0 (evaluation criteria and safety guidance expanded)
Modified principles: None
Modified sections: Evaluation and Acceptance; Safety and Human-Gated Release
Added sections: None
Removed sections: None
Deferred TODO: Original ratification date is unknown and requires confirmation.
-->

# Natural-Language Reminder Agent Constitution

## Core Principles

### I. Modular Python and API Contracts
The application MUST use Python 3.13 and FastAPI. Python modules MUST have clear,
cohesive responsibilities and explicit interfaces so parsing, validation, model
interaction, and HTTP handling can be tested independently. API behavior and
error responses MUST be explicit; invalid model output MUST NOT be returned as a
successful reminder.

### II. Local-Only Model Runtime
Inference MUST use TinyLlama served locally through Ollama. The application MUST
NOT call paid model APIs or require a paid external inference service. Model
identity, version or digest when available, Ollama configuration, and generation
parameters MUST be recorded for each evaluation run so results can be reproduced
as far as a non-deterministic model permits.

### III. Validated Structured Outputs
All model-produced reminder, clarification, or refusal results MUST be parsed
and validated against explicit Pydantic models before use. Schema validation
MUST reject missing, malformed, or out-of-range fields; natural-language output
alone is not a valid structured result. Validation failures MUST be visible in
the API or evaluation evidence and MUST NOT be silently coerced into success.

### IV. Layered, Repeatable Evaluation
Model quality MUST be evaluated with both deterministic checks and semantic
quality criteria; exact-string matching MUST NOT be the sole measure. Structural
schema checks, deterministic invariants, property-based or metamorphic checks,
and semantic/quality evaluation MUST all run through one evaluation harness.
The evaluation set MUST contain at least 15 distinct, meaningful cases, and
each case MUST be sampled at least three times to expose output variability.

### V. Safety and Human-Gated Release
The agent MUST ask for clarification when required date, time, timezone, or
recurrence details are missing or materially ambiguous; it MUST NOT invent
those details. It MUST preserve stated intent, handle unsafe or disallowed
requests according to the product safety policy, and never represent an
unvalidated or uncertain result as a confirmed reminder. Automated evaluation
MAY report evidence and a threshold result, but only a human may record the
final ACCEPT or REJECT decision. A critical safety failure includes, at a high
level, enabling imminent physical harm or self-harm, exposing sensitive
personal information, or producing a consequential reminder despite
materially unsafe ambiguity or invalid details. The feature specification
MUST define the exact disallowed request categories; this constitution does
not enumerate them.

## Evaluation and Acceptance

One harness MUST execute the complete evaluation set and produce a single
machine-readable report containing per-case outputs, validation results,
criterion-level failures, and the aggregate score. The harness MUST include:

- Structural validation of every generated result against its Pydantic schema.
- Deterministic invariant checks, including preservation of explicit user
  details, valid date/time values, and consistency of the selected outcome
  (reminder, clarification, or refusal).
- Property-based or metamorphic checks, including equivalent paraphrases
  preserving reminder meaning and a time-only change not altering unrelated
  fields.
- Semantic/quality checks for intent fidelity, appropriate clarification or
  refusal, and absence of unsupported assumptions. Criteria and expected
  outcomes MUST be written down for each case before evaluating a candidate.
  Every semantic evaluation criterion MUST have a documented pass/fail rule
  or scoring rubric before candidate evaluation begins.

The minimum evaluation set MUST cover at least these 16 distinct scenarios:

1. A clear one-time reminder with an explicit date and time.
2. A relative time anchored to a fixed evaluation clock.
3. A relative date that crosses a month boundary.
4. A relative date that crosses a year boundary.
5. A valid leap-day date.
6. An impossible calendar date.
7. A request missing a required date or time.
8. A materially ambiguous phrase such as "next Friday."
9. A timezone or daylight-saving-time ambiguity.
10. A recurring reminder with explicit weekdays and time.
11. A recurrence request with an unspecified required schedule detail.
12. Multiple reminders expressed in one request.
13. Conflicting date or time details in one request.
14. A request whose named subject must be preserved without invention.
15. A paraphrase pair that should produce equivalent reminder meaning.
16. An unsafe or policy-disallowed reminder request requiring safe handling.

For each evaluation run, the harness MUST use at least three independent
generation samples per case and record the prompt, model identity, generation
settings, evaluation-set version, outputs, and the fixed evaluation clock and
timezone. The evaluation clock and timezone MUST be recorded once per run and
reused unchanged across every sample in that run; the timezone MUST use an
explicit IANA identifier. A sample passes only when it is structurally valid,
satisfies every applicable deterministic invariant, and meets the case's
semantic/quality criteria. The aggregate score MUST be calculated as:

**passing samples / total evaluated samples * 100**

The total evaluated samples include every case sample in the run. Any critical
safety failure MUST set the aggregate score to zero. The single acceptance
threshold is **at least 90%**. The report MUST show the measured score and
whether the threshold was met; this constitution defines no completed
evaluation result.

## Repair, Evidence, and Release

Before any evidence-driven repair, the initial baseline snapshot MUST preserve
the evaluated application, prompts, model/configuration identifiers, harness,
case definitions, and baseline outputs or traces. Repairs MUST cite the failing
case, observed evidence, and violated criterion; changes without a reproduced
or documented failure are not evaluation-driven repairs.

After each repair, the complete harness MUST be rerun against the same
versioned evaluation set and recorded runtime settings. The initial snapshot
MUST remain unchanged. A separate final snapshot MUST preserve the repaired
candidate and its complete evaluation report, including failures; neither
snapshot may be overwritten by later runs. Comparisons MUST identify changed
artifacts and measured results without implying causality unsupported by the
evidence.

The harness result is evidence, not release authorization. A designated human
reviewer MUST inspect the final snapshot and report and explicitly record
**ACCEPT** or **REJECT**. No model, test runner, or automated workflow may make
that final decision on the reviewer's behalf.

## Governance

This constitution governs feature specifications, implementation, and
evaluation for the Natural-Language Reminder Agent. Amendments MUST be reviewed
for consistency with the assignment requirements, update this document, and
increment the version according to semantic versioning: MAJOR for incompatible
governance changes, MINOR for new or materially expanded principles, and PATCH
for clarifications that do not change requirements. Every amendment MUST update
the last-amended date and its version; the original ratification date MUST
remain unchanged.

Reviews MUST verify applicable principles and acceptance rules. Any exception
MUST be documented with its rationale, scope, risk, and human approver; it
cannot waive the human-only final decision or conceal evaluation failures.
When evidence is incomplete, the report MUST say so rather than imply success.

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption date unknown | **Last Amended**: 2026-11-11
