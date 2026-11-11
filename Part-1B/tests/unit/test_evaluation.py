import json
import shutil
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

import pytest

from reminder_agent.evaluation.reports import score_run
from reminder_agent.evaluation.repair_evidence import load_repair_evidence
from reminder_agent.evaluation.release_decision import record_release_decision
from reminder_agent.evaluation.run import (
    load_dataset,
    evaluate_dataset,
    run_service_error_gates,
    validate_run_parameters,
)
from reminder_agent.evaluation.metamorphic import time_only_change
from reminder_agent.evaluation.properties import run_property_checks
from reminder_agent.evaluation.adjudications import (
    apply_adjudications,
    load_adjudications,
    record_adjudication,
)
from reminder_agent.evaluation.run import build_report
from reminder_agent.services.ollama import ModelReply
from reminder_agent.evaluation.snapshots import create_snapshot

ROOT = Path(__file__).resolve().parents[2]


def clean_test_workdir(work: Path) -> None:
    shutil.rmtree(work)
    if work.parent.exists() and not any(work.parent.iterdir()):
        work.parent.rmdir()


def test_score_formula_and_threshold_are_exact():
    assert score_run(90, 100, False) == 90.0
    assert score_run(3, 4, False) == 75.0


def test_critical_safety_failure_forces_zero():
    assert score_run(100, 100, True) == 0.0


@pytest.mark.parametrize("samples", [0, 1, 2])
def test_evaluation_rejects_fewer_than_three_samples(samples):
    with pytest.raises(ValueError, match="at least 3"):
        validate_run_parameters(samples, "2026-03-01T12:00:00Z", "America/New_York")


def test_clock_requires_offset_and_timezone_requires_iana():
    with pytest.raises(ValueError, match="offset"):
        validate_run_parameters(3, "2026-03-01T12:00:00", "America/New_York")
    with pytest.raises(ValueError, match="IANA"):
        validate_run_parameters(3, "2026-03-01T12:00:00Z", "Not/AZone")


def test_dataset_retains_all_24_scenarios_with_two_service_gates():
    cases, _digest = load_dataset(ROOT / "evaluation" / "datasets" / "cases.jsonl")
    assert len(cases) == 24
    assert {case["case_id"] for case in cases if case.get("gate")} == {"E22", "E23"}
    assert all(
        len(case["requirement_trace"]) > 0
        for case in cases
    )


def test_service_error_gates_do_not_fabricate_outcomes():
    results = run_service_error_gates()
    assert results["E22"]["passed"]
    assert results["E23"]["passed"]
    assert not results["E22"]["fabricated_outcome"]


def test_time_only_relation_allows_only_declared_field_changes():
    before = {"intent": "create", "subject": "call", "due_at": "09:00", "timezone": "UTC"}
    after = {"intent": "create", "subject": "call", "due_at": "11:00", "timezone": "UTC"}
    assert time_only_change(before, after, ["due_at"])
    after["subject"] = "send a message"
    assert not time_only_change(before, after, ["due_at"])


def test_offline_generated_property_layer_passes_supported_boundaries():
    result = run_property_checks()
    assert result["generated_dates"] >= 100
    assert result["passed"]


def test_report_counts_paired_samples_and_does_not_decide_release():
    report = build_report(
        case_results=[{
            "case_id": "E15",
            "samples": [{
                "sample_index": 1,
                "passed": True,
                "critical_safety_failure": False,
                "paired_sample": {"passed": False, "critical_safety_failure": False},
            }],
        }],
        service_gates={"E22": {"passed": True}, "E23": {"passed": True}},
        cases=[{"dataset_version": "1.0.0"}],
        dataset_hash="sha256",
        clock=datetime(2026, 3, 1, 12, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        root=ROOT,
        property_results={"passed": True},
        run_id="report-test",
    )
    assert report["sample_denominator"] == 2
    assert report["passing_samples"] == 1
    assert report["score_percent"] == 50
    assert report["threshold_percent"] == 90
    assert report["evaluation_clock"] == "2026-03-01T12:00:00+00:00"
    assert report["evaluation_timezone"] == "America/New_York"
    assert report["final_human_decision"] is None


def test_harness_executes_both_metamorphic_generations_with_stubbed_model():
    class FakeOllama:
        def __init__(self, _settings):
            self.calls = 0

        async def generate(self, prompt):
            self.calls += 1
            time_value = "11:30" if "11:30 AM" in prompt else "09:30"
            subject = "call my dentist" if "my dentist" in prompt else "call the dentist"
            content = json.dumps({
                "outcome": "reminder",
                "actions": [{
                    "intent": "create",
                    "subject": subject,
                    "due_at": f"2026-03-05T{time_value}:00-05:00",
                    "timezone": "America/New_York",
                    "recurrence": None,
                    "target_reference": None,
                }],
            })
            return ModelReply(content, "tinyllama:1.1b-chat-v0.6-q4_0", "sha256:stub", {"temperature": 0.2}, prompt)

        async def close(self):
            return None

    cases, _hash = load_dataset(ROOT / "evaluation" / "datasets" / "cases.jsonl")
    selected = [case for case in cases if case["case_id"] in {"E15", "E16"}]
    clock = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
    fake = FakeOllama(None)
    case_results, gates, properties = asyncio.run(
        evaluate_dataset(
            selected,
            1,
            clock,
            "America/New_York",
            ROOT,
            model_client_factory=lambda _settings: fake,
        )
    )
    assert fake.calls == 4
    assert all(result["samples"][0]["metamorphic_relation"]["passed"] for result in case_results)
    assert all(result["samples"][0]["passed"] for result in case_results)
    assert all(result["samples"][0]["paired_sample"]["passed"] for result in case_results)
    assert gates["E22"]["passed"] and gates["E23"]["passed"]
    assert properties["passed"]


def test_human_adjudication_is_preflagged_semantic_only_and_append_only():
    work = ROOT / ".test-artifacts" / f"adjudication-{uuid4().hex}"
    work.mkdir(parents=True)
    try:
        case = {
            "case_id": "E99",
            "adjudication_required": True,
            "adjudication_rubric": "Use the recorded context to decide intent fidelity.",
            "adjudication_criteria": ["intent_outcome"],
            "semantic_criteria": ["intent_outcome", "clarification"],
            "critical_safety": False,
        }
        record = {
            "case_id": "E99",
            "sample_index": 1,
            "sample_kind": "primary",
            "criterion": "intent_outcome",
            "reviewer": "Human Reviewer",
            "timestamp": "2026-03-01T12:00:00Z",
            "evidence": "Two supported normalized readings remain.",
            "decision": "PASS",
            "rationale": "The selected interpretation matches the supplied wording.",
        }
        destination = work / "adjudications.jsonl"
        record_adjudication(case, record, destination)
        loaded = load_adjudications(destination)
        results, used = apply_adjudications(
            {"intent_outcome": False, "clarification": True},
            case,
            1,
            "primary",
            loaded,
        )
        assert results == {"intent_outcome": True, "clarification": True}
        assert len(used) == 1
        with pytest.raises(ValueError, match="already exists"):
            record_adjudication(case, record, destination)

        unsafe_case = {**case, "critical_safety": True}
        unsafe_results, _ = apply_adjudications(
            {"intent_outcome": False}, unsafe_case, 1, "primary", loaded
        )
        assert unsafe_results["intent_outcome"] is False
    finally:
        clean_test_workdir(work)


def test_snapshot_is_immutable_and_records_hashes():
    work = ROOT / ".test-artifacts" / f"snapshot-{uuid4().hex}"
    work.mkdir(parents=True)
    try:
        report = work / "report.json"
        report.write_text(json.dumps({"score_percent": 0}), encoding="utf-8")
        destination = create_snapshot(
            ROOT, report, "initial", "unit-run", snapshot_root=work / "snapshots"
        )
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["final_release_decision"] is None
        assert "report.json" in manifest["artifacts"]
        with pytest.raises(FileExistsError):
            create_snapshot(
                ROOT, report, "initial", "unit-run", snapshot_root=work / "snapshots"
            )
    finally:
        clean_test_workdir(work)


def test_repair_evidence_must_cite_a_failed_case_and_initial_snapshot():
    work = ROOT / ".test-artifacts" / f"repair-{uuid4().hex}"
    work.mkdir(parents=True)
    try:
        report = work / "baseline.json"
        report.write_text(json.dumps({
            "run_id": "baseline-run",
            "cases": [{
                "case_id": "E01",
                "samples": [{
                    "sample_index": 1,
                    "structural": {"passed": True},
                    "invariants": {"time_zone_offset": True},
                    "semantic_criteria": {"temporal_correctness": False},
                }],
            }],
        }), encoding="utf-8")
        snapshot = create_snapshot(
            ROOT,
            report,
            "initial",
            "baseline-run",
            snapshot_root=work / "snapshots",
        )
        evidence = work / "repairs.jsonl"
        evidence.write_text(json.dumps({
            "baseline_report": str(report),
            "baseline_snapshot_manifest": str(snapshot / "manifest.json"),
            "case_id": "E01",
            "sample_index": 1,
            "evidence_sample": "primary",
            "criterion": "temporal_correctness",
            "change_summary": "Corrected the relative-time boundary validation.",
        }) + "\n", encoding="utf-8")
        records = load_repair_evidence(evidence)
        assert records[0]["observed_failure"] is True
        assert records[0]["baseline_run_id"] == "baseline-run"
    finally:
        clean_test_workdir(work)


def test_human_release_decision_is_append_only_and_separate_from_snapshot():
    work = ROOT / ".test-artifacts" / f"release-{uuid4().hex}"
    work.mkdir(parents=True)
    try:
        report = work / "final.json"
        report.write_text(json.dumps({"final_human_decision": None}), encoding="utf-8")
        snapshot = create_snapshot(
            ROOT, report, "final", "final-run", snapshot_root=work / "snapshots"
        )
        manifest_path = snapshot / "manifest.json"
        decision_path = record_release_decision(
            manifest_path, "Reviewer", "REJECT", "Observed unresolved failures.", work / "decisions"
        )
        record = json.loads(decision_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert record["decision"] == "REJECT"
        assert manifest["final_release_decision"] is None
        with pytest.raises(FileExistsError):
            record_release_decision(
                manifest_path, "Reviewer", "REJECT", "Duplicate record.", work / "decisions"
            )
    finally:
        clean_test_workdir(work)
