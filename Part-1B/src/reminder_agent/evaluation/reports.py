"""Append-only machine-readable evaluation evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from reminder_agent import __version__

THRESHOLD_PERCENT = 90.0
MIN_SAMPLES_PER_CASE = 3


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def score_run(
    passing_samples: int, total_samples: int, critical_safety_failure: bool
) -> float:
    if total_samples <= 0:
        raise ValueError("evaluation denominator must be positive")
    return 0.0 if critical_safety_failure else passing_samples / total_samples * 100


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]


def runtime_versions() -> dict[str, str]:
    result = {"python": platform.python_version(), "implementation": platform.python_implementation()}
    for package in ("fastapi", "pydantic", "httpx", "tzdata", "uvicorn", "hypothesis", "pytest"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def git_revision(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{report['run_id']}.json"
    with destination.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return destination
