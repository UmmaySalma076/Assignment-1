# Research: Natural-Language Reminder Agent

## Decisions

### Ollama transport and constrained output

- **Decision**: Use the local Ollama `POST /api/chat` endpoint with
  `stream: false`. Pass the Pydantic v2 `model_json_schema()` result in Ollama's
  `format` field, reinforce the contract in the prompt, then call local
  `model_validate_json()` on the returned message content.
- **Rationale**: Ollama documents both non-streaming chat responses and passing
  a JSON schema to `format`; its guidance explicitly recommends Pydantic schema
  generation and local validation. Constrained generation is a formatting aid,
  not a substitute for application validation.
- **Alternatives considered**: plain text/JSON prompting without schema
  constraint was rejected because it offers weaker structure; a paid hosted
  model or hosted judge violates the constitution.
- **Caveat**: Documentation establishes API support, not reliable adherence by
  every model build. Pin the exact configured tag to
  `tinyllama:1.1b-chat-v0.6-q4_0`; verify it can be loaded and exercised.
  Record that tag, the actual Ollama model digest when available, and complete
  generation settings for every evaluation sample. Treat malformed output or
  any invariant violation as `502 INVALID_MODEL_OUTPUT`; no remote fallback.
  A clarification may return 200 only when missing or ambiguous user input
  justifies it and the clarification itself passes schema and consistency
  validation. Invalid output is never converted into clarification.

### FastAPI and strict Pydantic response unions

- **Decision**: Use strict Pydantic v2 request and outcome models, a
  discriminator on `outcome`, and FastAPI response models/OpenAPI schemas.
  Customize request validation handling to return the planned stable
  `400 INVALID_REQUEST` envelope.
- **Rationale**: FastAPI documents response-model validation, serialization,
  filtering, and OpenAPI generation. Pydantic recommends discriminated unions
  for predictable selection of one variant. This matches the required
  reminder/clarification/refusal contract and prevents union ambiguity.
- **Alternatives considered**: untagged/ordered unions were rejected because
  branch selection is less explicit; returning arbitrary dictionaries was
  rejected because it weakens validation and generated API contracts.

### Deterministic IANA timezone validation

- **Decision**: Use Python `datetime` and `zoneinfo.ZoneInfo` for date/time
  parsing and IANA-zone checks. Detect DST gaps/folds by constructing local
  candidates with each `fold` value and round-tripping through UTC; clarify
  when the local time is nonexistent or ambiguous. Validate that the returned
  RFC 3339 offset corresponds to the declared IANA zone at that instant.
- **Rationale**: Python's standard library implements IANA time zones and the
  `fold` mechanism for ambiguous transitions. Python documentation notes that
  Windows has no well-known system timezone database locations; therefore
  include the first-party `tzdata` package so `ZoneInfo` can resolve zones
  consistently on Windows.
- **Alternatives considered**: trusting the model to compute offsets or
  dates was rejected because date validity and timezone consistency are
  deterministic invariants. A third-party date parser is unnecessary for
  validating normalized structured values.
- **Caveat**: Timezone rules can change as tzdata is updated; record Python and
  tzdata versions in evaluation reports and snapshots.

### Semantic evaluation without an LLM judge

- **Decision**: Use a deterministic scorer over human-authored case
  expectations: normalized intent/outcome, explicit slots, canonical aliases,
  allowed field differences, and the spec's pass/fail criteria. Encode
  pass/fail rules for every criterion that can be mechanically checked.
  Restrict human adjudication to cases explicitly flagged before the run where
  two or more interpretations remain genuinely plausible after normalization;
  record each adjudication separately with case/sample, criterion, reviewer,
  timestamp, evidence, decision, and rationale.
- **Rationale**: The criteria are documented before candidate runs and the
  scorer can execute without a paid API or secondary model. Routine samples
  receive deterministic scoring; genuinely ambiguous cases receive narrowly
  scoped rubric-based human review. Per-sample evidence remains inspectable,
  and final ACCEPT/REJECT remains a distinct human-only release decision.
- **Fail-closed rule**: Missing adjudication for a pre-flagged ambiguous
  criterion is a criterion failure. Human adjudication must not override a
  structural failure, deterministic invariant failure, or critical safety
  failure.
- **Alternatives considered**: an LLM judge, including a separate local model
  judge, was rejected to avoid paid inference and an additional stochastic
  authority in the acceptance calculation. Exact-string matching was rejected
  by the constitution.

### Stable API error mapping

- **Decision**: Valid reminder, clarification, and refusal outcomes use HTTP
  200. Malformed or oversized input maps to 400/`INVALID_REQUEST`; invalid
  model output to 502/`INVALID_MODEL_OUTPUT`; Ollama unavailable to
  503/`OLLAMA_UNAVAILABLE`; Ollama timeout to 504/`OLLAMA_TIMEOUT`; unexpected
  failures to 500/`INTERNAL_ERROR`.
- **Rationale**: A valid clarification/refusal is a successful interpretation
  result, while invalid model output and local dependency failures are distinct
  from user input and from valid model outcomes. This plan resolves the
  specification's open status/code decision.
- **Alternatives considered**: default framework 422 responses were rejected
  in favor of one stable documented client-input error envelope. The API must
  install a FastAPI validation exception handler to enforce this mapping.

### Request-size limit

- **Decision**: Limit request `text` to 2000 Unicode code points. Reject longer
  text with HTTP 400 and `INVALID_REQUEST`; do not truncate or send it to
  Ollama. Configure the effective `MAX_REQUEST_CHARS` from 1 to 2000, with
  default 2000; the published API schema retains 2000 as its hard ceiling.
  The stable error envelope is
  `{"error":{"code":"INVALID_REQUEST","message":"..."}}`. Publish
  `maxLength: 2000` in OpenAPI and enforce the effective configured limit in
  Pydantic.
- **Rationale**: The bound is explicit, testable, and protects the local
  service from unbounded prompts without silently changing user intent.

### Recurrence end conditions

- **Decision**: A finite recurrence end condition contains exactly one of
  `until` or `occurrences`. `until` is an inclusive valid local date in the
  recurrence timezone and cannot precede the first occurrence. `occurrences`
  is a positive total count including the first occurrence. A null end
  condition is permitted only for an explicitly indefinite schedule.
- **Rationale**: Mutual exclusivity removes contradictory termination rules;
  deterministic validation rejects both selectors, neither selector in a
  present object, invalid dates, and non-positive counts.

## Sources

- Ollama, Structured Outputs:
  <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama, Chat API:
  <https://docs.ollama.com/api/chat>
- FastAPI, Response Model:
  <https://fastapi.tiangolo.com/tutorial/response-model/>
- Pydantic v2, Unions and Discriminated Unions:
  <https://docs.pydantic.dev/latest/concepts/unions/>
- Python 3.13, `zoneinfo`:
  <https://docs.python.org/3.13/library/zoneinfo.html>
- Python 3.13, `datetime`:
  <https://docs.python.org/3.13/library/datetime.html>
- FastAPI, Error Handling:
  <https://fastapi.tiangolo.com/tutorial/handling-errors/>
