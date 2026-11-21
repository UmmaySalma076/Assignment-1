"""Append-only human release decisions kept separate from evaluation results."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from reminder_agent.evaluation.reports import digest_bytes


def record_release_decision(
    snapshot_manifest: Path,
    reviewer: str,
    decision: str,
    rationale: str,
    output_dir: Path,
) -> Path:
    if decision not in {"ACCEPT", "REJECT"}:
        raise ValueError("decision must be ACCEPT or REJECT")
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("reviewer and rationale are required")
    manifest_path = snapshot_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "final":
        raise ValueError("release review must reference a final snapshot")
    report_bytes = (manifest_path.parent / "report.json").read_bytes()
    report_sha256 = digest_bytes(report_bytes)
    if report_sha256 != manifest.get("artifacts", {}).get("report.json"):
        raise ValueError("final report does not match the snapshot manifest")
    if decision == "ACCEPT" and json.loads(report_bytes).get("evaluation_decision") != "PASS":
        raise ValueError("ACCEPT requires a passing final evaluation")
    record = {
        "snapshot_run_id": manifest["run_id"],
        "snapshot_manifest": str(manifest_path),
        "report_sha256": report_sha256,
        "reviewer": reviewer.strip(),
        "decision": decision,
        "rationale": rationale.strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{manifest['run_id']}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(record, file, indent=2)
        file.write("\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--decision", required=True, choices=("ACCEPT", "REJECT"))
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--output", default="artifacts/release-decisions")
    args = parser.parse_args(argv)
    try:
        path = record_release_decision(
            Path(args.snapshot_manifest),
            args.reviewer,
            args.decision,
            args.rationale,
            Path(args.output),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
