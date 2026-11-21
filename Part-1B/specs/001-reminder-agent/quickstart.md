# Local Setup and Validation Guide

The service interprets reminder requests locally and returns a proposed
reminder, clarification, or refusal. Storage, scheduling and delivery are
outside this application’s scope.

## Prerequisites and installation

- Python 3.13
- Git
- Ollama running on the same machine
- Local storage for `tinyllama:1.1b-chat-v0.6-q4_0`

From `Part-1B` in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Start Ollama using the platform's service manager or `ollama serve`, then
download the exact configured model:

```powershell
ollama pull tinyllama:1.1b-chat-v0.6-q4_0
ollama list
```

The application pins the tag and rejects model overrides. It accepts only a
local Ollama host; no paid or remote model fallback is configured.

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "tinyllama:1.1b-chat-v0.6-q4_0"
$env:OLLAMA_CONNECT_TIMEOUT_SECONDS = "5"
$env:OLLAMA_READ_TIMEOUT_SECONDS = "120"
$env:MAX_REQUEST_CHARS = "2000"
```

`MAX_REQUEST_CHARS` defaults to 2000 Unicode code points and accepts only
values from 1 through 2000. Text above the effective limit returns HTTP 400
`INVALID_REQUEST` without truncation or model submission. `OLLAMA_MODEL` must
remain exactly `tinyllama:1.1b-chat-v0.6-q4_0`.

## Run the API locally

```powershell
python -m uvicorn reminder_agent.api.app:app --reload
```

Liveness does not call Ollama; readiness checks local `/api/tags` without
generating a response:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Example interpretation request:

```powershell
$body = @{
  text = "Remind me to call the dentist on 2026-03-05 at 9:30 AM"
  timezone = "America/New_York"
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/reminders/interpret `
  -ContentType "application/json" -Body $body
```

The request/response contract is also described in
[contracts/openapi.yaml](./contracts/openapi.yaml). Production rejects the
evaluation-only `reference_time` request field. Valid reminders are proposals,
not confirmation that anything was saved or delivered.

## Tests and evaluation

Run deterministic, API, contract, and property-based tests without invoking
Ollama:

```powershell
python -m pytest
```

The single evaluation entry point retains all 24 dataset scenarios. It scores
E01–E21 and E24 with at least three independent model generations per case;
E22–E23 are separately reported service-error gates and do not enter the model
sample denominator. G06 separately tests malformed JSON and configured
request-length rejection before inference. Each run uses the fixed clock and
IANA timezone declared in its dataset. For example:

```powershell
python .harness/run.py `
  --dataset evals/dataset.json `
  --output artifacts\evaluations `
  --clock 2026-03-01T12:00:00Z `
  --timezone America/New_York `
  --samples-per-case 3
```

The runner requires at least three samples per case and writes a new
machine-readable report for each run. The default evaluation generates 72
scored samples, counting both generations in each E15 and E16 pair. The score
is passing model samples divided by all evaluated model samples times 100.
The threshold is 90%, and a critical safety failure forces the score to zero.
The report records case-to-requirement traces, prompts, output, results for
each evaluation layer, the fixed context, runtime versions, the model tag and
digest when available, generation parameters, errors, service gates, and the
sample denominator. The command prints the report location and the decision.
Exit code `0` means `PASS`, `1` means the run produced a non-passing decision,
and `2` means the command could not complete.

## Evidence-based repair and release review

Before any evaluation-driven repair, preserve the baseline report and snapshot:

```powershell
python .harness/run.py --snapshot-stage initial
```

Each repair must cite the observed failing case, evidence, and criterion.
After a repair, run the complete harness again against the same versioned
dataset, clock, timezone, and recorded runtime settings. Preserve a distinct
final snapshot:

```powershell
python .harness/run.py `
  --snapshot-stage final `
  --repair-evidence evaluation\repairs.jsonl
```

Each JSONL repair record must cite an earlier `baseline_report` and its
`baseline_snapshot_manifest`, the failing `case_id`, `sample_index`,
`evidence_sample` (`primary` or `paired`), failed `criterion`, and
`change_summary`. The runner verifies the failure against that report and the
initial snapshot before it records the repair.

Snapshots are written to unique `artifacts/snapshots/initial/<run-id>/` and
`artifacts/snapshots/final/<run-id>/` directories. The student reviews the final
report and records their own ACCEPT or REJECT, rationale, known limitations
and residual risks in `evidence/harness-log.md`. ACCEPT requires an automated
PASS. The sidecar command below links the same human decision to its snapshot.
Supply the reviewed run ID, your name, your actual decision and your own rationale.

```powershell
python -m reminder_agent.evaluation.release_decision `
  --snapshot-manifest "evidence/final-generation/REPLACE_WITH_RUN_ID/manifest.json" `
  --reviewer "Reviewer Name" `
  --decision "ACCEPT_OR_REJECT" `
  --rationale "Your assessment of the evidence, limitations and residual risks." `
  --output evidence/release-decisions
```

### Stable errors

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Invalid fields, invalid context, evaluation-only time in production, or text above the configured limit. |
| 502 | `INVALID_MODEL_OUTPUT` | Malformed/schema-invalid model output or a deterministic invariant failure; never converted into a success or clarification. |
| 503 | `OLLAMA_UNAVAILABLE` | The local Ollama endpoint or pinned model is unavailable. |
| 504 | `OLLAMA_TIMEOUT` | Local Ollama exceeded a configured timeout. |
| 500 | `INTERNAL_ERROR` | Sanitized unexpected service failure. |

Valid and justified clarifications/refusals use HTTP 200 and contain no
actionable reminder data.
