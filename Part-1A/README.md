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
  [snapshot provenance](evidence/final-generation/checkout-portability.provenance.json).
- The student records the final decision and justification after reviewing the
  run and the [harness log](specs/001-smart-todo/evidence/harness-log.md). See
  [Task T051](specs/001-smart-todo/tasks.md#phase-7-harness-v2-and-remediation) for the
  review file and supporting evidence.
