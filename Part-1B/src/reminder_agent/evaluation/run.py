"""Single local-only evaluation entry point for the versioned scenario set."""

from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from reminder_agent.api.app import create_app
from reminder_agent.api.errors import ServiceException
from reminder_agent.config import PINNED_MODEL, Settings
from reminder_agent.contracts.models import (
    OUTCOME_ADAPTER,
    InterpretRequest,
    ReminderResponse,
)
from reminder_agent.evaluation.invariants import check_invariants
from reminder_agent.evaluation.adjudications import (
    apply_adjudications,
    load_adjudications,
)
from reminder_agent.evaluation.metamorphic import compare_equivalent, time_only_change
from reminder_agent.evaluation.properties import run_property_checks
from reminder_agent.evaluation.reports import (
    MIN_SAMPLES_PER_CASE,
    THRESHOLD_PERCENT,
    digest_bytes,
    git_revision,
    new_run_id,
    runtime_versions,
    score_run,
    write_report,
)
from reminder_agent.evaluation.repair_evidence import load_repair_evidence
from reminder_agent.evaluation.semantic import score_semantics
from reminder_agent.evaluation.snapshots import create_snapshot
from reminder_agent.evaluation.structural import validate_structure
from reminder_agent.services.interpreter import Interpreter
from reminder_agent.services.ollama import (
    GENERATION_SETTINGS,
    ModelReply,
    OllamaClient,
    PROMPT_PATH,
)


class RecordingModel:
    def __init__(self, client: OllamaClient):
        self.client = client
        self.last_reply: ModelReply | None = None

    async def generate(self, prompt: str) -> ModelReply:
        self.last_reply = await self.client.generate(prompt)
        return self.last_reply


def load_dataset(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    ids = [case["case_id"] for case in cases]
    required = {f"E{number:02d}" for number in range(1, 25)}
    if len(cases) != 24 or set(ids) != required or len(ids) != len(set(ids)):
        raise ValueError("dataset must contain exactly one case for every E01–E24 scenario")
    for case in cases:
        if case["dataset_version"] != "1.0.0":
            raise ValueError("unsupported dataset version")
    return cases, digest_bytes(raw)


def validate_run_parameters(
    samples_per_case: int, clock_text: str, timezone_name: str
) -> datetime:
    if samples_per_case < MIN_SAMPLES_PER_CASE:
        raise ValueError(f"samples-per-case must be at least {MIN_SAMPLES_PER_CASE}")
    try:
        ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError("timezone must be a valid IANA identifier") from exc
    clock = datetime.fromisoformat(clock_text.replace("Z", "+00:00"))
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("clock must include a UTC offset")
    return clock.astimezone(timezone.utc)


def run_service_error_gates() -> dict[str, dict[str, Any]]:
    class FakeModel:
        def __init__(self, result: str | Exception):
            self.result = result

        async def generate(self, _prompt: str) -> ModelReply:
            if isinstance(self.result, Exception):
                raise self.result
            return ModelReply(self.result, PINNED_MODEL, None, {}, "")

    checks = {
        "E22": (FakeModel("not json"), 502, "INVALID_MODEL_OUTPUT"),
        "E23_unavailable": (
            FakeModel(ServiceException(503, "OLLAMA_UNAVAILABLE", "unavailable")),
            503,
            "OLLAMA_UNAVAILABLE",
        ),
        "E23_timeout": (
            FakeModel(ServiceException(504, "OLLAMA_TIMEOUT", "timed out")),
            504,
            "OLLAMA_TIMEOUT",
        ),
    }
    results: dict[str, dict[str, Any]] = {}
    settings = Settings()
    for gate, (model, expected_status, expected_code) in checks.items():
        client = TestClient(create_app(settings, model))
        try:
            response = client.post(
                "/v1/reminders/interpret",
                json={"text": "Remind me to call home on 2026-03-05 at 9:00 AM UTC."},
            )
        finally:
            client.close()
        body = response.json()
        passed = (
            response.status_code == expected_status
            and body.get("error", {}).get("code") == expected_code
            and "outcome" not in body
            and "actions" not in body
        )
        results[gate] = {
            "passed": passed,
            "status_code": response.status_code,
            "expected_status_code": expected_status,
            "error_code": body.get("error", {}).get("code"),
            "expected_error_code": expected_code,
            "fabricated_outcome": "outcome" in body or "actions" in body,
        }
    results["E23"] = {
        "passed": results["E23_unavailable"]["passed"] and results["E23_timeout"]["passed"],
        "subchecks": {
            "unavailable": results.pop("E23_unavailable"),
            "timeout": results.pop("E23_timeout"),
        },
    }
    return results


async def evaluate_dataset(
    cases: list[dict[str, Any]],
    samples_per_case: int,
    clock: datetime,
    eval_timezone: str,
    root: Path,
    model_client_factory: Callable[[Settings], Any] = OllamaClient,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    property_results = run_property_checks()
    settings = Settings.from_env()
    adjudications = load_adjudications(
        root / "evaluation" / "rubrics" / "adjudications.jsonl"
    )
    model_client = model_client_factory(settings)
    recording = RecordingModel(model_client)
    interpreter = Interpreter(recording)
    case_results: list[dict[str, Any]] = []
    try:
        for case in cases:
            if case.get("gate"):
                continue
            trusted = case.get("trusted_context", {})
            request_data: dict[str, Any] = {
                "text": case["request"],
                "timezone": trusted.get("timezone", eval_timezone),
                "reference_time": clock.isoformat(),
                "reminder_context": trusted.get("reminder_context", []),
            }
            request = InterpretRequest.model_validate_json(json.dumps(request_data))
            samples: list[dict[str, Any]] = []
            for sample_index in range(1, samples_per_case + 1):
                primary = await _evaluate_one(
                    request,
                    case,
                    clock,
                    eval_timezone,
                    model_client,
                    recording,
                    interpreter,
                    sample_index,
                    "primary",
                    adjudications,
                )
                primary_outcome = primary.pop("_outcome")
                sample_record = {"sample_index": sample_index, **primary}
                pair_spec = case.get("metamorphic_pair")
                if pair_spec:
                    pair_request_data = dict(request_data)
                    pair_request_data["text"] = pair_spec["request"]
                    pair_request = InterpretRequest.model_validate_json(
                        json.dumps(pair_request_data)
                    )
                    pair_case = deepcopy(case)
                    if "expected_actions" in pair_spec:
                        pair_case["expected_actions"] = pair_spec["expected_actions"]
                    paired = await _evaluate_one(
                        pair_request,
                        pair_case,
                        clock,
                        eval_timezone,
                        model_client,
                        recording,
                        interpreter,
                        sample_index,
                        "paired",
                        adjudications,
                    )
                    paired_outcome = paired.pop("_outcome")
                    if pair_spec["relation"] == "equivalent":
                        relation_passed = compare_equivalent(
                            primary_outcome, paired_outcome
                        )
                    else:
                        before = (
                            primary_outcome.actions[0].model_dump(mode="json")
                            if isinstance(primary_outcome, ReminderResponse)
                            and primary_outcome.actions
                            else {}
                        )
                        after = (
                            paired_outcome.actions[0].model_dump(mode="json")
                            if isinstance(paired_outcome, ReminderResponse)
                            and paired_outcome.actions
                            else {}
                        )
                        relation_passed = bool(before and after) and time_only_change(
                            before, after, pair_spec.get("allowed_field_differences", [])
                        )
                    for result in (primary, paired):
                        result["semantic_criteria"]["metamorphic_relation"] = relation_passed
                        result["passed"] = (
                            result["error"] is None
                            and result["structural"]["passed"]
                            and all(result["invariants"].values())
                            and all(result["semantic_criteria"].values())
                        )
                    sample_record["paired_sample"] = paired
                    sample_record["metamorphic_relation"] = {
                        "type": pair_spec["relation"],
                        "passed": relation_passed,
                        "allowed_field_differences": pair_spec.get(
                            "allowed_field_differences", []
                        ),
                    }
                    sample_record.update(primary)
                samples.append(sample_record)
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "scenario": case["scenario"],
                    "requirement_trace": case["requirement_trace"],
                    "sample_count": len(samples),
                    "generation_count": sum(
                        1 + ("paired_sample" in item) for item in samples
                    ),
                    "samples": samples,
                }
            )
    finally:
        await model_client.close()
    return case_results, run_service_error_gates(), property_results


async def _evaluate_one(
    request: InterpretRequest,
    case: dict[str, Any],
    clock: datetime,
    eval_timezone: str,
    model_client: OllamaClient,
    recording: RecordingModel,
    interpreter: Interpreter,
    sample_index: int,
    sample_kind: str,
    adjudications: list[dict[str, Any]],
) -> dict[str, Any]:
    recording.last_reply = None
    raw_output: str | None = None
    error: dict[str, str] | None = None
    outcome = None
    attempted_prompt = interpreter._build_prompt(
        request, clock, request.timezone or eval_timezone
    )
    try:
        if case.get("critical_safety"):
            reply = await model_client.generate(attempted_prompt)
            recording.last_reply = reply
            raw_output = reply.content
            valid, outcome, parse_error = validate_structure(raw_output)
            if not valid:
                error = {"code": "INVALID_MODEL_OUTPUT", "message": parse_error or ""}
            elif outcome is not None:
                interpreter._validate_outcome(
                    outcome, request, request.timezone, clock
                )
        else:
            outcome = await interpreter.interpret(
                request, clock=clock, timezone_name=request.timezone
            )
            if recording.last_reply is not None:
                raw_output = recording.last_reply.content
    except ServiceException as exc:
        error = {"code": exc.code, "message": exc.message}
    except ValueError as exc:
        error = {"code": "INVALID_MODEL_OUTPUT", "message": str(exc)}
    except Exception as exc:
        error = {"code": "INTERNAL_ERROR", "message": str(exc)}

    candidate: str | dict[str, Any]
    if raw_output is not None:
        candidate = raw_output
    else:
        candidate = outcome.model_dump(mode="json") if outcome else {}
    valid, parsed, parse_error = validate_structure(candidate)
    if valid:
        outcome = parsed
    structural = {"passed": valid, "error": parse_error}
    invariants = check_invariants(outcome, case) if valid else {"schema": False}
    semantics = score_semantics(outcome, case) if valid else {
        criterion: False for criterion in case.get("semantic_criteria", [])
    }
    semantics, used_adjudications = apply_adjudications(
        semantics, case, sample_index, sample_kind, adjudications
    )
    critical_failure = bool(case.get("critical_safety")) and (
        outcome is None or getattr(outcome, "outcome", None) != "refusal"
    )
    reply = recording.last_reply
    passed = (
        error is None
        and structural["passed"]
        and all(invariants.values())
        and all(semantics.values())
    )
    return {
        "prompt": reply.prompt if reply else attempted_prompt,
        "model_tag": reply.model_tag if reply else PINNED_MODEL,
        "model_digest": reply.model_digest if reply else None,
        "generation_settings": reply.generation_settings if reply else dict(GENERATION_SETTINGS),
        "raw_output": raw_output,
        "parsed_output": outcome.model_dump(mode="json") if outcome else None,
        "structural": structural,
        "invariants": invariants,
        "semantic_criteria": semantics,
        "adjudications": used_adjudications,
        "critical_safety_failure": critical_failure,
        "passed": passed,
        "error": error,
        "_outcome": outcome,
    }


def build_report(
    case_results: list[dict[str, Any]],
    service_gates: dict[str, dict[str, Any]],
    cases: list[dict[str, Any]],
    dataset_hash: str,
    clock: datetime,
    timezone_name: str,
    root: Path,
    property_results: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    samples = [
        result
        for case in case_results
        for sample in case["samples"]
        for result in (
            (sample, sample["paired_sample"])
            if "paired_sample" in sample
            else (sample,)
        )
    ]
    passing = sum(sample["passed"] for sample in samples)
    safety_failure = any(sample["critical_safety_failure"] for sample in samples)
    score = score_run(passing, len(samples), safety_failure)
    settings = Settings.from_env()
    return {
        "run_id": run_id or new_run_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": cases[0]["dataset_version"],
        "dataset_sha256": dataset_hash,
        "prompt_version": "1",
        "prompt_sha256": digest_bytes(PROMPT_PATH.read_bytes()),
        "code_revision": git_revision(root),
        "model": {
            "endpoint_class": "local_ollama",
            "configured_tag": PINNED_MODEL,
            "base_url": settings.ollama_base_url,
            "connect_timeout_seconds": settings.connect_timeout_seconds,
            "read_timeout_seconds": settings.read_timeout_seconds,
            "digest_recorded_per_sample_when_available": True,
            "generation_settings_recorded_per_sample": True,
        },
        "runtime_versions": runtime_versions(),
        "evaluation_clock": clock.isoformat(),
        "evaluation_timezone": timezone_name,
        "clock_reused_for_all_samples": True,
        "timezone_reused_for_all_samples": True,
        "cases": case_results,
        "service_error_gates": service_gates,
        "property_checks": property_results,
        "required_gates_passed": property_results["passed"]
        and all(gate["passed"] for gate in service_gates.values()),
        "sample_denominator": len(samples),
        "passing_samples": passing,
        "score_formula": "passing samples / total evaluated samples * 100",
        "score_percent": score,
        "threshold_percent": THRESHOLD_PERCENT,
        "threshold_met": score >= THRESHOLD_PERCENT,
        "critical_safety_override": safety_failure,
        "repairs": [],
        "final_human_decision": None,
    }


async def execute(args: argparse.Namespace) -> Path:
    root = Path(__file__).resolve().parents[3]
    dataset_path = Path(args.dataset).resolve()
    cases, dataset_hash = load_dataset(dataset_path)
    clock = validate_run_parameters(args.samples_per_case, args.clock, args.timezone)
    case_results, gates, property_results = await evaluate_dataset(
        cases, args.samples_per_case, clock, args.timezone, root
    )
    report = build_report(
        case_results,
        gates,
        cases,
        dataset_hash,
        clock,
        args.timezone,
        root,
        property_results,
    )
    if args.repair_evidence:
        report["repairs"] = load_repair_evidence(Path(args.repair_evidence).resolve())
    report_path = write_report(Path(args.output), report)
    if args.snapshot_stage:
        create_snapshot(
            root,
            report_path,
            args.snapshot_stage,
            report["run_id"],
            Path(args.snapshot_root).resolve() if args.snapshot_root else None,
        )
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="evaluation/datasets/cases.jsonl")
    parser.add_argument("--output", default="artifacts/evaluations")
    parser.add_argument("--clock", default="2026-03-01T12:00:00Z")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--samples-per-case", type=int, default=3)
    parser.add_argument("--snapshot-stage", choices=("initial", "final"))
    parser.add_argument("--snapshot-root")
    parser.add_argument(
        "--repair-evidence",
        help="Local JSON/JSONL records citing failures from an earlier report.",
    )
    args = parser.parse_args(argv)
    try:
        report_path = asyncio.run(execute(args))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
