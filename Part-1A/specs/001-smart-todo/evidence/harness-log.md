## Harness Log: Part 1A (Smart Todo API)

**Status:** Draft put together from our repo evidence. T050 and T051 are still unchecked in `tasks.md`.

## 1. Context & Background

Before we started coding, Copilot had access to our approved Spec Kit specs:

- Constitution v1.0.0 (ratified back on 2026-11-08). We later bumped it to v1.1.0 on 2026-11-09, but those new v1.1.0 gates weren't part of this initial run.

- Smart Todo feature spec (specs/001-smart-todo/spec.md).

- Implementation plan (specs/001-smart-todo/plan.md).

- Ordered implementation task list (specs/001-smart-todo/tasks.md).

For reference, the Git history points to Copilot agent session 545198b7-512e-4fee-8552-6e50ea100bba. (The specific model name wasn't captured in the logs, so I'm leaving it at that).

## 2. Initial Code generation

The first cut gave us the initial Smart Todo API along with its contract, integration, and unit tests. You can find the raw snapshot under evidence/initial-generation/initial-code-state.zip and the unpacked source files in evidence/initial-generation/initial-source/.

## 3. Harness

Our `.harness/run.py` script runs six automated checks:

1. **syntax** — `compileall` for `app` and `tests`.
2. **lint** — `ruff check . --config .harness/ruff.toml`; a zero exit status is required.
3. **security** — `bandit -r app -ll -q`; a zero exit status is required.
4. **tests+coverage** — all pytest tests with `app/` coverage and an 85% minimum.
5. **traceability** — every FR/NFR ID found in the active spec must also appear in our Python tests.
6. **guardrails** — scans `app/` and `tests/` for `# noqa`/`# nosec`, and verifies the Ruff configuration against its recorded SHA-256 hash.

Quick note: The constitution rules mean we aren't allowed to mess with `.harness/ruff.toml` or patch `.harness/run.py` just to bypass errors. The guardrails verify the ruff config hash, but keep in mind they don't automatically check if someone secretly weakened a test assertion or cleared out history files.

## 4. Run history

All the run reports are saved under `evidence/results/` at the Part-1A root. Here is how the sequence went:

| Run | Result | Failed gate(s) | Short reason |
|-----|--------|----------------|--------------|
| run1 | FAIL | lint, traceability | Ruff found 11 long lines: 3 in `.harness/run.py` and 8 in application/test code. All 21 FR/NFR IDs were missing from tests. |
| run2 | FAIL — embedded report | lint | The file is not valid JSON as a whole because PowerShell command text precedes an embedded run2 JSON object. The embedded report records Ruff lint failure; the other five gates passed. |
| run3 | FAIL | lint | Three remaining E501 long-line findings in `.harness/run.py` (lines 1, 24, and 92 in that run). |
| run4 | FAIL | lint | Same three `.harness/run.py` line-length findings. |
| run5 | FAIL | lint | Same three `.harness/run.py` line-length findings. |
| run6 | FAIL | lint | Same three `.harness/run.py` line-length findings. |
| run7 | PASS | None | All six gates passed; pytest reported 30 passed and 87.66% total `app/` coverage. The report also recorded dependency deprecation/resource warnings. |

Saved reports include: `harness-run1-20261108T201551Z.json`,
`harness-run2-20261108T202045Z.json` (contaminated, but its embedded JSON reports a
lint failure), `harness-run3-20261108T202120Z.json`,
`harness-run4-20261108T202129Z.json`, `harness-run5-20261108T202136Z.json`,
`harness-run6-20261108T202146Z.json`, and
`harness-run7-20261108T202911Z.json`.

## 5. Failures and How We Fixed Them

### Repair cycle A: Controlled IDs and strict status validation

- **The bug:** The controlled-ID test threw a `TypeError` because `TaskRepository` wasn't taking an `id_generator` argument. Also, passing a string like `"false"` for a status was returning an HTTP 200 instead of a 422 validation error.

- **What Copilot changed:** Added an optional test ID generator while keeping SQLite auto-generation for production, and tightened up the status validation so it strictly expects booleans.

- **Verification:** Targeted tests passed successfully (`evidence/results/targeted-repair-tests-rerun.txt`).

### Repair cycle B: Structured logging and an incorrect test selection

- **The bug:** Our logging test initially couldn't find any `task.created` events. Once we added logging, a targeted assertion accidentally grabbed the first POST request log record when it was actually expecting the later GET record.

- **What Copilot changed:** Added clean structured JSON log formatting and proper event triggers, and we fixed the test query to explicitly target the GET request record.

- **Verification:** Focused assertions passed cleanly.

### Repair cycle C: Archived Ruff baseline finding

- **The bug:** Scanning the archived initial source kicked up a B008 warning on a FastAPI dependency default.

- **What Copilot changed:** Cleaned up active route dependencies to use `Annotated` and excluded the archived initial-source folder from Ruff rather than turning off rules globally.

- **Verification:** `python -m ruff check` . passed cleanly on active code

### Repair cycle D: FR/NFR traceability and Harness run1 lint

- **The bug:** Run 1 flagged that all 21 requirement IDs were missing from our tests, alongside 11 long lines.

- **What Copilot changed:** Added clear requirement-ID docstrings across the test suite and built an integration test listing 1,000 tasks. Cleaned up line wrapping on the app/test files without dropping any assertions.

- **Verification:** Run 7 showed traceability passing, all 30 tests green, and 87.66% coverage.

### Fixing the Harness itself: line lengths in `.harness/run.py`

Run 1 caught E501 errors inside the harness script itself (lines 1, 24, and 92). Because these weren't application bugs, runs 3 through 6 kept failing on the exact same harness lines.

I checked out commit `ed3bf59` (`Part 1A: fix line lengths in harness script, run7` by `UmmaySalma076`), which simply reformatted the module docstring, subprocess arguments, and report dictionary across multiple lines without touching any test or gate logic. Once that was done, Run 7 passed linting with flying colors.

## 6. Integrity & Trust Check

- The Run 7 report confirms that traceability and guardrails passed, verifying 21 requirement IDs and zero `# noqa/# nosec` shortcuts in `app/` or `tests/`.

- Remember that the guardrails gate only verifies the Ruff config hash—it doesn't magically ensure no tests were weakened or files edited behind the scenes, so we still need to rely on our Git history review for that.

- Run 2's raw log is corrupted/non-JSON, so don't try to parse it automatically.

- Commit `ed3bf59` is purely cosmetic line-wrapping for the harness script.

## 7. Known limitations

- We hit 30 passing tests and 87.66% coverage (beating our 85% goal), but you'll see a minor Starlette/httpx deprecation warning and a couple of SQLite ResourceWarning notices about unclosed connections in the logs.

- The 1,000-task performance check ran fine locally, but it's not a heavy load test.

- Bandit came back clean with -ll, but this is a simple local SQLite single-user API; full auth and multi-user concurrency aren't tested here.

- Tasks T044 through T051 are still sitting unchecked in specs/001-smart-todo/tasks.md. T050 requires us to wrap up this log, and T051 needs a fresh human sign-off once everything is verified.

## 8. Final human decision

**Previously recorded decision:** ACCEPT  
**Date:** 2026-11-09  
**Justification (from `evidence/results/human-review.json`):** Accepted
the earlier implementation based on its final validation report: syntax, Ruff,
pytest (28 passed), and Bandit passed, with the deprecation warning treated as
non-blocking.

**Harness v2 decision:** PENDING — the existing ACCEPT predates the run7 Harness v2
report and does not complete T051. A human must review the Harness v2 reports,
repair evidence, final snapshot, and this log, then record a new decision and
justification. This draft does not make that decision.