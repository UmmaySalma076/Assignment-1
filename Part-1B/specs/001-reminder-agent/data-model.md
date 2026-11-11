# Data Model: Natural-Language Reminder Agent

This design models proposed interpretation and evaluation evidence only. It
does not define persistent reminder storage or notification delivery.

## API and Domain Records

### InterpretRequest

| Field | Type | Constraints |
|---|---|---|
| `text` | string | Required; non-empty after trimming; effective configurable maximum `MAX_REQUEST_CHARS` defaults to and cannot exceed 2000 Unicode code points; user-supplied and untrusted. Longer input returns HTTP 400 `INVALID_REQUEST`; it is never truncated. |
| `timezone` | string or null | Optional trusted IANA timezone; reject unknown zone identifiers. |
| `reference_time` | RFC 3339 datetime or null | Optional trusted input for controlled evaluation only; production API rejects caller-supplied values. |
| `reminder_context` | list of `ReminderReference` | Optional trusted context, default empty. |

### ReminderReference

| Field | Type | Constraints |
|---|---|---|
| `reference` | string | Required unique identifier within the supplied context. |
| `subject` | string | Required non-empty description used only to resolve a target. |
| `due_at` | RFC 3339 datetime or null | Optional trusted current due time. |
| `timezone` | IANA timezone or null | Optional trusted context; must be compatible with supplied due time. |
| `recurrence` | `Recurrence` or null | Optional trusted current schedule; required as context when a recurring reminder is being rescheduled and its schedule must be preserved. |

### ReminderResponse

| Field | Type | Constraints |
|---|---|---|
| `outcome` | literal `"reminder"` | Discriminator. |
| `actions` | list of `ReminderAction` | At least one action. No duplicate/conflicting operations. |

### ReminderAction

| Field | Type | Constraints |
|---|---|---|
| `intent` | enum | `create`, `reschedule`, or `snooze`. |
| `subject` | string | Required, non-empty, preserve requested subject. |
| `due_at` | RFC 3339 datetime with offset | Must be a real calendar instant and offset must match `timezone`. |
| `timezone` | IANA timezone | Must be resolvable by `zoneinfo`. |
| `recurrence` | `Recurrence` or null | Null means one-time action. |
| `target_reference` | string or null | Null for create; required and unique in trusted context for reschedule/snooze. |

### Recurrence

| Field | Type | Constraints |
|---|---|---|
| `frequency` | enum | `daily`, `weekly`, `monthly`, `yearly`. |
| `interval` | positive integer | Number of frequency units between occurrences. |
| `weekdays` | list of weekday enum or null | Required for weekly; at least one unique weekday. |
| `day_of_month` | integer or null | Required for monthly; 1-31. Months without this day are skipped. |
| `month` | integer or null | Required for yearly; 1-12. |
| `day` | integer or null | Required for yearly; valid day for month, including Feb 29. Feb 29 occurs only in leap years. |
| `timezone` | IANA timezone | Required; schedule is interpreted in this zone. |
| `end_condition` | `RecurrenceEnd` or null | Null only when the user explicitly requests an indefinite schedule. |

Selectors inconsistent with the selected frequency are invalid.
For `snooze`, recurrence must be null because snooze creates a one-time
postponement. A reschedule of a recurring reminder may preserve its recurrence
only when that schedule is present in trusted reference context; otherwise the
agent asks for clarification.

### RecurrenceEnd

Exactly one end selector is present when the recurrence is not explicitly
indefinite. The selectors are mutually exclusive; supplying both or neither is
invalid:

- `until`: valid, inclusive local calendar date in the recurrence timezone.
  The date must not precede the first scheduled occurrence's local date.
- `occurrences`: positive total number of scheduled occurrences, including
  the first occurrence.

For an explicitly requested indefinite recurrence, the whole
`end_condition` is null. A present end condition must contain exactly one
non-null selector. Pydantic and deterministic domain validation reject both
selectors together, neither selector in a non-null object, invalid dates,
non-positive counts, and end dates before the first occurrence.

### ClarificationResponse

| Field | Type | Constraints |
|---|---|---|
| `outcome` | literal `"clarification"` | Discriminator. |
| `question` | string | Required, focused, user-understandable question. |
| `unresolved_fields` | list of string | At least one field/conflict; no reminder actions. |

### RefusalResponse

| Field | Type | Constraints |
|---|---|---|
| `outcome` | literal `"refusal"` | Discriminator. |
| `category` | stable high-level enum | No hidden model reasoning. |
| `message` | string | Required concise safe explanation; no reminder actions. |

### ServiceError

| Field | Type | Constraints |
|---|---|---|
| `error.code` | stable string enum | `INVALID_REQUEST`, `INVALID_MODEL_OUTPUT`, `OLLAMA_UNAVAILABLE`, `OLLAMA_TIMEOUT`, or `INTERNAL_ERROR`. |
| `error.message` | string | Sanitized, user-safe description. |

## Evaluation Records

### EvaluationCase

Contains `case_id`, dataset version, requirement trace IDs, scenario/request,
trusted context, expected outcome and canonical semantic slots, applicable
invariant IDs, semantic criterion IDs and pass rules, metamorphic group and
allowed field differences, and critical-safety classification/rationale. A
case may set `adjudication_required` only when genuinely plausible
interpretations remain after deterministic normalization; it must include the
prewritten rubric and evidence requirements.

### EvaluationSample

Contains `case_id`, sample index, prompt/model identifiers,
pinned TinyLlama tag `tinyllama:1.1b-chat-v0.6-q4_0`, actual Ollama model
digest when available, and complete effective generation settings for that
sample. Also records output text and parsed object, schema result, invariant
results, semantic results, separately recorded human adjudication only when
required, critical-safety result, and final sample pass/fail.

A human adjudication record includes case/sample IDs, criterion, reviewer,
timestamp, evidence, decision, and rationale. It is separate from
machine-scored criterion results and cannot override structural, deterministic
invariant, or critical-safety failures.

### EvaluationRun

Contains unique run ID, code/dataset/prompt hashes, fixed clock and IANA
timezone, pinned model tag, actual model digest when available and generation
settings recorded per sample, all 24 specification scenario results (with
E22-E23 as separate service-error gates), sample counts,
per-case records, aggregate pass count/denominator/score, threshold status,
safety override, service gates, and initial/final snapshot manifest
references. The run clock and timezone are immutable run-level fields reused
by all samples.

## State and Validation Invariants

- Valid model outcome union: exactly one of reminder, clarification, refusal.
- Clarification/refusal must not contain actionable actions.
- A clarification is eligible as an HTTP 200 outcome only when the request or
  trusted context establishes the cited missing/ambiguous user information and
  the clarification passes the full schema and consistency validation.
- Any other model schema failure or invariant violation is a 502
  `INVALID_MODEL_OUTPUT`; it must not be rewritten into a clarification.
- Create has no target; reschedule/snooze has exactly one supplied target.
- Every action carries a valid RFC 3339 offset matching its IANA timezone.
- Ambiguous/nonexistent local wall times yield clarification; no guessed fold.
- Recurrence contains only selectors valid for its frequency.
- The evaluation sample passes only if structural validation, all applicable
  invariants, and every semantic criterion pass.
- Run score is passing sample count divided by all evaluated model samples,
  multiplied by 100. At least 90% is required; any critical safety failure
  forces zero.

## Relationships

- One `InterpretRequest` produces one `ReminderResponse`,
  `ClarificationResponse`, or `RefusalResponse`, or a service error.
- One `ReminderResponse` contains one or more `ReminderAction` records.
- A `ReminderAction` has zero or one `Recurrence` and zero or one
  `ReminderReference` target, with target required for reschedule/snooze.
- One `EvaluationRun` references one immutable dataset version and contains
  all 24 specification scenario records. Each scored case (E01-E21 and E24)
  produces at least three independent `EvaluationSample` records; E22-E23
  produce separate service-error gate records and do not enter the model-sample
  denominator.
