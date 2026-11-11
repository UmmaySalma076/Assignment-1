"""Verify that recorded candidate repairs cite observed baseline failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_repair_evidence(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    try:
        parsed = json.loads(text)
        records = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    verified: list[dict[str, Any]] = []
    for record in records:
        verified.append(_verify_record(record))
    return verified


def _verify_record(record: Any) -> dict[str, Any]:
    required = {
        "baseline_report",
        "baseline_snapshot_manifest",
        "case_id",
        "sample_index",
        "evidence_sample",
        "criterion",
        "change_summary",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise ValueError(f"repair evidence must include {sorted(required)}")
    if not isinstance(record["sample_index"], int) or record["sample_index"] < 1:
        raise ValueError("repair sample_index must be a positive integer")
    if record["evidence_sample"] not in {"primary", "paired"}:
        raise ValueError("evidence_sample must be primary or paired")
    if not all(str(record[field]).strip() for field in ("case_id", "criterion", "change_summary")):
        raise ValueError("repair case, criterion, and change summary must not be empty")

    report_path = Path(record["baseline_report"]).resolve()
    snapshot_path = Path(record["baseline_snapshot_manifest"]).resolve()
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    if snapshot.get("stage") != "initial" or snapshot.get("run_id") != report.get("run_id"):
        raise ValueError("repair evidence must reference an initial snapshot for its baseline report")
    if snapshot.get("artifacts", {}).get("report.json") != hashlib.sha256(
        report_bytes
    ).hexdigest():
        raise ValueError("baseline report does not match the initial snapshot manifest")
    case = next(
        (item for item in report.get("cases", []) if item.get("case_id") == record["case_id"]),
        None,
    )
    sample = next(
        (
            item
            for item in (case or {}).get("samples", [])
            if item.get("sample_index") == record["sample_index"]
        ),
        None,
    )
    if record["evidence_sample"] == "paired":
        sample = (sample or {}).get("paired_sample")
    if sample is None:
        raise ValueError("repair evidence references an unknown baseline case/sample")
    failed = _criterion_failed(sample, record["criterion"])
    if not failed:
        raise ValueError("repair evidence criterion did not fail in the referenced baseline sample")
    return {
        "baseline_run_id": report["run_id"],
        "baseline_report": str(report_path),
        "baseline_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "baseline_snapshot_manifest": str(snapshot_path),
        "baseline_snapshot_manifest_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "case_id": record["case_id"],
        "sample_index": record["sample_index"],
        "evidence_sample": record["evidence_sample"],
        "criterion": record["criterion"],
        "change_summary": record["change_summary"],
        "observed_failure": True,
    }


def _criterion_failed(sample: dict[str, Any], criterion: str) -> bool:
    if criterion == "schema":
        return not sample.get("structural", {}).get("passed", False)
    for group in ("invariants", "semantic_criteria"):
        results = sample.get(group, {})
        if criterion in results:
            return results[criterion] is False
    return False
