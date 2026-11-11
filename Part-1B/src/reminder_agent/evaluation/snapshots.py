"""Non-overwriting evidence snapshots for human release review."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SnapshotStage = Literal["initial", "final"]
PRESERVED_PATHS = (
    ".gitignore",
    "pyproject.toml",
    "src",
    "tests",
    "evaluation/datasets",
    "evaluation/rubrics",
    "specs/001-reminder-agent",
)


def create_snapshot(
    root: Path,
    report_path: Path,
    stage: SnapshotStage,
    run_id: str,
    snapshot_root: Path | None = None,
) -> Path:
    destination = (snapshot_root or root / "artifacts" / "snapshots") / stage / run_id
    destination.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    for relative in PRESERVED_PATHS:
        source = root / relative
        if source.is_dir():
            target = destination / "candidate" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)
            copied.extend(
                str(path.relative_to(destination))
                for path in target.rglob("*")
                if path.is_file()
            )
        elif source.is_file():
            target = destination / "candidate" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(str(target.relative_to(destination)))
    report_target = destination / "report.json"
    shutil.copy2(report_path, report_target)
    copied.append("report.json")
    manifest = {
        "stage": stage,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            path: hashlib.sha256((destination / path).read_bytes()).hexdigest()
            for path in sorted(copied)
        },
        "final_release_decision": None,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return destination
