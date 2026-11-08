from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "specs" / "001-smart-todo" / "evidence"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and preserve Smart Todo validation evidence.")
    parser.add_argument("--label", required=True, help="Short evidence label, such as post-repair.")
    return parser.parse_args()


def create_code_snapshot(snapshot_path: Path) -> None:
    included_paths = [
        PROJECT_ROOT / "app",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "scripts" / "run_harness.py",
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "README.md",
    ]
    with ZipFile(snapshot_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in included_paths:
            if path.is_file():
                archive.write(path, path.relative_to(PROJECT_ROOT))
                continue
            for source_file in path.rglob("*"):
                if (
                    source_file.is_file()
                    and "__pycache__" not in source_file.parts
                    and ".pytest_cache" not in source_file.parts
                    and source_file.suffix != ".pyc"
                ):
                    archive.write(source_file, source_file.relative_to(PROJECT_ROOT))


def main() -> int:
    args = parse_args()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,49}", args.label) is None:
        raise SystemExit("The evidence label must be 1-50 safe filename characters.")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    evidence_prefix = f"{args.label}-{timestamp}"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_path = EVIDENCE_DIR / f"{evidence_prefix}-code.zip"
    report_path = EVIDENCE_DIR / f"{evidence_prefix}-report.json"
    log_path = EVIDENCE_DIR / f"{evidence_prefix}.log"
    create_code_snapshot(snapshot_path)

    checks = [
        ("syntax", [sys.executable, "-m", "compileall", "-q", "app", "tests"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("bandit", [sys.executable, "-m", "bandit", "-r", "app"]),
    ]
    report: dict[str, object] = {
        "label": args.label,
        "captured_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "code_snapshot": snapshot_path.name,
        "checks": [],
    }

    with log_path.open("w", encoding="utf-8") as log_file:
        for name, command in checks:
            log_file.write(f"## {name}\n$ {' '.join(command)}\n")
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            log_file.write(output)
            if not output.endswith("\n"):
                log_file.write("\n")
            log_file.write(f"exit_code: {result.returncode}\n\n")
            report["checks"].append(
                {
                    "name": name,
                    "command": command,
                    "exit_code": result.returncode,
                    "output": output,
                }
            )
            print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}")

    failed_checks = [
        check["name"]
        for check in report["checks"]
        if check["exit_code"] != 0
    ]
    report["failed_checks"] = failed_checks
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Evidence log: {log_path}")
    print(f"Evidence report: {report_path}")
    print(f"Code snapshot: {snapshot_path}")
    return 1 if failed_checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
