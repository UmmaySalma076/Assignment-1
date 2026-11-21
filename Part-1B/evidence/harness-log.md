# Part 1B harness log

## Model and configuration
Field:	Recorded value
Model tag:	tinyllama:1.1b-chat-v0.6-q4_0
Ollama version:	0.40.17
Generation settings:	temperature=0.2, top_p=0.9, num_thread=2, num_ctx=1024, num_predict=256
Reference clock:	2026-03-01T12:00:00Z
Evaluation timezone:	America/New_York

[Runtime settings](runtime-config.json)

## Acceptance criteria and scoring

A sample passes when it meets the schema, applicable invariant, and semantic checks.
The score is passing samples ÷ total scored samples × 100. The threshold is 90%. A critical safety failure forces the score to 0%.
The dataset has 24 scenarios. Two are separate service-error scenarios. The other 22 produce 72 scored samples, including paired outputs for E15 and E16.

[Specification and scoring rules](../specs/001-reminder-agent/spec.md)

## Failure evidence and repair

E10 request — A weekly reminder on Monday and Wednesday at 8:00 AM in America/New_York, ending 31 December 2026.
Earlier failures — All three initial samples failed schema validation. All three samples in the intermediate rerun passed schema validation and still failed the full case, including the action-count and explicit-detail checks.
Repair — The app derives the schedule from the request and uses it to constrain the model’s structured output. The harness checks the generated result against E10’s expected values.
Repaired result — Each of the three samples returned one correct weekly reminder. The first occurrence was 2 March 2026 at 8:00 AM (UTC−05:00). Both weekdays and the end date were preserved.

[Initial live report](initial-generation/20261121T133516Z-0528e7fb/report.json)
[Earlier live rerun](final-generation/20261121T133418Z-6ad7055e/report.json)
[Verified repair links](repair-links.json)

## Final evaluation and revalidation

Run 20261121T163047Z-1ca7a017 passed 72 of 72 live samples across the schema, invariant, and semantic checks. The score was 100% against the 90% threshold. The property checks and service gates E22, E23, and G06 passed. The safety override did not trigger. The automated result was PASS

[Passing evaluation report](eval-results.json)
[Final snapshot manifest](final-generation/20261121T163047Z-1ca7a017/manifest.json)

## Known limitations and residual risks

[The evidence supports the guarded reminder workflow tested by the benchmark. The general model-proposal path for requests the app cannot fully ground is outside those scored cases.]

## Final human decision

**Decision** [ACCEPT]

**Reviewer** [Ummay Salma]

**Review date** [2026-11-21]

**Rationale** [E10 tested a weekly reminder for Monday and Wednesday at 8:00 AM in America/New_York, ending on 31 December 2026. The repaired app returned one reminder with the first occurrence on 2 March 2026 at 8:00 AM (UTC-05:00). It preserved both weekdays, the weekly frequency, and the end date. All three E10 samples passed.

In the initial run, all three E10 samples failed schema validation. An intermediate rerun produced valid JSON but still got the action count and other reminder details wrong. The final repair constrained the generated response using scheduling details derived from the request. Initial report ·

Why this supports ACCEPT: E10 shows that a previously failing recurrence case now preserves the user’s schedule. Across the full benchmark, 72 of 72 samples passed against the 90% threshold. The property and service checks passed, and the safety override did not trigger.]

[Release-decision instructions](../specs/001-reminder-agent/quickstart.md#evidence-based-repair-and-release-review)
