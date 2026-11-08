"""Part 1A harness. Usage: python .harness/run.py --label NAME   |   python .harness/run.py --lock"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / ".harness"
RESULTS = ROOT / "evidence" / "results"
SPEC = ROOT / "specs" / "001-smart-todo" / "spec.md"
LOCK = HARNESS / "protected.sha256"
PROTECTED = [HARNESS / "ruff.toml"]
ID_PATTERN = re.compile(r"\b(?:NFR|FR)-\d{3}\b")
FORBIDDEN = re.compile(r"#\s*(noqa|nosec)", re.IGNORECASE)


def sh(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"exit_code": p.returncode, "stdout": p.stdout[-6000:], "stderr": p.stderr[-3000:]}


def gate(name: str, passed: bool, detail: dict) -> dict:
    return {"gate": name, "passed": passed, **detail}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traceability() -> dict:
    spec_ids = set(ID_PATTERN.findall(SPEC.read_text(encoding="utf-8")))
    test_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("*.py"))
    missing = sorted(spec_ids - set(ID_PATTERN.findall(test_text)))
    return gate("traceability", not missing, {
        "expected": f"every spec ID appears in tests ({len(spec_ids)} IDs)",
        "observed": f"missing from tests: {missing}" if missing else "all IDs referenced",
    })


def guardrails() -> dict:
    problems = []
    for folder in ("app", "tests"):
        for f in (ROOT / folder).rglob("*.py"):
            if FORBIDDEN.search(f.read_text(encoding="utf-8")):
                problems.append(f"suppression comment in {f.relative_to(ROOT)}")
    if not LOCK.exists():
        problems.append("protected.sha256 missing (run --lock once)")
    else:
        locked = json.loads(LOCK.read_text())
        for p in PROTECTED:
            if locked.get(p.name) != digest(p):
                problems.append(f"protected file changed: {p.name}")
    return gate("guardrails", not problems, {
        "expected": "no noqa/nosec; protected config unchanged",
        "observed": problems or "ok",
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label")
    ap.add_argument("--lock", action="store_true")
    args = ap.parse_args()
    if args.lock:
        LOCK.write_text(json.dumps({p.name: digest(p) for p in PROTECTED}, indent=2))
        print("Locked:", LOCK)
        return 0
    if not args.label:
        raise SystemExit("--label is required")

    py = sys.executable
    gates = []
    for name, cmd in [
        ("syntax", [py, "-m", "compileall", "-q", "app", "tests"]),
        ("lint", [py, "-m", "ruff", "check", ".", "--config", ".harness/ruff.toml"]),
        ("security", [py, "-m", "bandit", "-r", "app", "-ll", "-q"]),
        ("tests+coverage", [py, "-m", "pytest", "-q", "--cov=app", "--cov-fail-under=85"]),
    ]:
        r = sh(cmd)
        gates.append(gate(name, r["exit_code"] == 0, {"command": " ".join(cmd[1:]), **r}))
    gates += [traceability(), guardrails()]

    overall = all(g["passed"] for g in gates)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"label": args.label, "captured_at": stamp, "overall": "PASS" if overall else "FAIL", "gates": gates}
    out = RESULTS / f"harness-{args.label}-{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for g in gates:
        print(f"{'PASS' if g['passed'] else 'FAIL'}  {g['gate']}")
    print(f"OVERALL: {report['overall']}  ->  {out.relative_to(ROOT)}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())