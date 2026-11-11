"""Narrowly scoped, pre-flagged human semantic adjudications."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "case_id",
    "sample_index",
    "sample_kind",
    "criterion",
    "reviewer",
    "timestamp",
    "evidence",
    "decision",
    "rationale",
}


def record_adjudication(
    case: dict[str, Any], record: dict[str, Any], destination: Path
) -> None:
    if case.get("adjudication_required") is not True:
        raise ValueError("case was not pre-flagged for human adjudication")
    adjudication_criteria = case.get("adjudication_criteria", [])
    if not case.get("adjudication_rubric") or not adjudication_criteria:
        raise ValueError("pre-flagged case must include its adjudication rubric")
    if not REQUIRED_FIELDS.issubset(record):
        raise ValueError(f"adjudication must include {sorted(REQUIRED_FIELDS)}")
    if record["case_id"] != case.get("case_id"):
        raise ValueError("adjudication case_id does not match the pre-flagged case")
    if record["criterion"] not in adjudication_criteria:
        raise ValueError("adjudication criterion is not pre-flagged for this case")
    if record["decision"] not in {"PASS", "FAIL"}:
        raise ValueError("adjudication decision must be PASS or FAIL")
    if record["sample_kind"] not in {"primary", "paired"}:
        raise ValueError("sample_kind must be primary or paired")
    if not isinstance(record["sample_index"], int) or record["sample_index"] < 1:
        raise ValueError("sample_index must be a positive integer")
    for field in ("reviewer", "evidence", "rationale"):
        if not str(record[field]).strip():
            raise ValueError(f"{field} must not be empty")
    timestamp = datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("adjudication timestamp must include a timezone offset")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = load_adjudications(destination)
        if any(
            item.get("case_id") == record["case_id"]
            and item.get("sample_index") == record["sample_index"]
            and item.get("sample_kind") == record["sample_kind"]
            and item.get("criterion") == record["criterion"]
            for item in existing
        ):
            raise ValueError("an adjudication already exists for this criterion and sample")
    with destination.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_adjudications(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        if not REQUIRED_FIELDS.issubset(record):
            raise ValueError("adjudication record is missing required fields")
    keys = [
        (
            item["case_id"],
            item["sample_index"],
            item["sample_kind"],
            item["criterion"],
        )
        for item in records
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate adjudication record")
    return records


def apply_adjudications(
    results: dict[str, bool],
    case: dict[str, Any],
    sample_index: int,
    sample_kind: str,
    records: list[dict[str, Any]],
) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    if case.get("adjudication_required") is not True:
        return results, []
    matching = [
        record
        for record in records
        if record.get("case_id") == case.get("case_id")
        and record.get("sample_index") == sample_index
        and record.get("sample_kind") == sample_kind
    ]
    used: list[dict[str, Any]] = []
    adjudicated = dict(results)
    for criterion in set(case.get("adjudication_criteria", [])):
        record = next((item for item in matching if item.get("criterion") == criterion), None)
        if case.get("critical_safety") or record is None:
            adjudicated[criterion] = False
        else:
            adjudicated[criterion] = record["decision"] == "PASS"
            used.append(record)
    return adjudicated, used
