# Part 1B · Natural-Language Reminder Agent

The FastAPI app uses a local TinyLlama model to interpret a reminder request.
It returns a proposed create, reschedule or snooze action, a clarification, or
a refusal. Storage and notifications are outside the application’s scope.

## Run locally

Install Python 3.13 and Ollama. Run these commands from `Part-1B` on macOS or
Linux. The quickstart includes the equivalent Windows setup and an API demo.
[Quickstart](specs/001-reminder-agent/quickstart.md)

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

Start Ollama with `ollama serve` if its service is stopped, then pull the exact
model tag and start the application. Open `http://127.0.0.1:8000/docs` to try
`POST /v1/reminders/interpret` and `GET /health/ready`.

```bash
ollama pull tinyllama:1.1b-chat-v0.6-q4_0
python -m uvicorn reminder_agent.api.app:app
```

## Evaluate

With Ollama running, use the single harness from `Part-1B`. It writes a new
JSON report and, when requested, an initial or final snapshot. The defaults
use three samples per scored case, a fixed clock of `2026-03-01T12:00:00Z`,
and `America/New_York` as the evaluation timezone.

```bash
python .harness/run.py --snapshot-stage initial
```

The harness checks schema conformance, deterministic invariants and properties,
and semantic fidelity. A sample counts toward the score when it passes every
applicable check. The target is 90%, with the prescribed zero-score override
for a critical safety failure. There are 24 dataset scenarios. E22 and E23
are separate service-error gates, and E15 and E16 each include a paired
generation. The default run scores 72 samples across the remaining 22 cases.
The separate G06 gate checks that malformed and oversized requests get
`INVALID_REQUEST` before a model call.
[Dataset](evals/dataset.json) · [Semantic rubric](evaluation/rubrics/semantic-rubrics.json)

## Specification and evidence

- [Constitution](.specify/memory/constitution.md)
- [Specification and clarifications](specs/001-reminder-agent/spec.md)
- [Technical plan](specs/001-reminder-agent/plan.md)
- [Requirements checklist](specs/001-reminder-agent/checklists/requirements.md)
- [Specification consistency review](specs/001-reminder-agent/analysis.md)
- [Implementation tasks](specs/001-reminder-agent/tasks.md)
- [API contract](specs/001-reminder-agent/contracts/openapi.yaml)
- [Versioned model prompt](src/reminder_agent/prompts/reminder_system.txt)
- [Evaluation results](evidence/eval-results.json)
- [Initial generation evidence](evidence/initial-generation/)
- [Final generation evidence](evidence/final-generation/)
- [Recorded model and runtime settings](evidence/runtime-config.json)
- [Recurrence and relative-time regression evidence](evidence/results/)

The initial live run evaluates the original application with the repaired
harness. The final run evaluates the revised application and prompt against
the same cases. Both reports record an automated FAIL. Each archived run
contains a report, a manifest, and a ZIP containing the evaluated candidate.

Write your own observations and ACCEPT or REJECT decision in
`evidence/harness-log.md` after reviewing the reports, repairs, remaining
failures, and residual risks. ACCEPT requires an automated PASS. The
quickstart shows how to save a separate decision record for the archived run.
