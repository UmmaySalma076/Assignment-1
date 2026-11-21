# Smart Todo Application

The Smart Todo API uses FastAPI and SQLite to create, list, retrieve, update,
complete, and delete tasks. The [specification](specs/001-smart-todo/spec.md)
defines the expected behavior.

## Run locally

From `Part-1A`, create a virtual environment with Python 3.13 and install the
project and harness dependencies.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Use the [Windows setup commands](specs/001-smart-todo/quickstart.md#local-setup)
from PowerShell. Open `http://127.0.0.1:8000/docs` to try the API.

## Run the deterministic harness

Run the harness from a Git checkout with the virtual environment active.

```bash
python .harness/run.py --label local-verification
```

The runner checks syntax, Ruff, Bandit, pytest with at least 85% application
coverage, requirement traceability, and guardrails. It saves timestamped JSON
reports under `artifacts/harness/`. Use `--output-dir PATH` to select a different
output location.

## Review evidence

- Initial code and archived runs are in [evidence](evidence/). The proposed
  release and its validation report are linked in the
  [snapshot provenance](evidence/final-generation/human-review-workflow.provenance.json).
- [Task T051](specs/001-smart-todo/tasks.md#phase-7-harness-v2-and-remediation) lists
  the reports and source snapshots to examine before recording your decision.

## Record your human review

1. Review the evidence and [harness log](specs/001-smart-todo/evidence/harness-log.md).
2. Create `evidence/results/human-review-v2.json`. Use a JSON object with
   `decision` (`ACCEPT` or `REJECT`), `reviewer` (your name), `decision_date`
   (YYYY-MM-DD), `justification` (your own reasoning), and `evidence` (an array
   of paths to the evidence you reviewed, relative to `Part-1A`).
3. Update the harness log with your own review, including the decision,
   rationale, and known limitations. Mark T051 complete in
   `specs/001-smart-todo/tasks.md`.
4. From `Part-1A`, run the following with your virtual environment active.

```bash
python .harness/run.py --lock
python .harness/run.py --label human-review
git add .harness/protected.sha256 evidence/results/human-review-v2.json specs/001-smart-todo/tasks.md specs/001-smart-todo/evidence/harness-log.md
git commit -m "Record Smart Todo human review"
python .harness/run.py --label committed-human-review
```

The guardrail checks the review record's format when T051 is complete.
The release decision is the `ACCEPT` or `REJECT` you record after reviewing the evidence.
