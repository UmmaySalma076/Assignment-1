"""Part 1A harness.

Usage:
    python .harness/run.py --label NAME
    python .harness/run.py --lock
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import io
import json
import re
import subprocess
import sys
import tokenize
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / ".harness"
RESULTS = ROOT / "evidence" / "results"
SPEC = ROOT / "specs" / "001-smart-todo" / "spec.md"
TASKS = ROOT / "specs" / "001-smart-todo" / "tasks.md"
PLAN = ROOT / "specs" / "001-smart-todo" / "plan.md"
CONSTITUTION = ROOT / ".specify" / "memory" / "constitution.md"
PYPROJECT = ROOT / "pyproject.toml"
LOCK = HARNESS / "protected.sha256"
RUFF_CONFIG = HARNESS / "ruff.toml"
ID_PATTERN = re.compile(r"\b(?:NFR|FR)-\d{3}\b")
FORBIDDEN = re.compile(r"#\s*(noqa|nosec)", re.IGNORECASE)
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)"
        r"\s*[:=]\s*['\"]?(?!<|your|example|change|placeholder)"
        r"[A-Za-z0-9/+_=-]{24,}"
    ),
]
COVERAGE_MINIMUM = 85
GATE_COMMANDS = {
    "syntax": ["-m", "compileall", "-q", "app", "tests"],
    "lint": ["-m", "ruff", "check", ".", "--config", ".harness/ruff.toml"],
    "security": ["-m", "bandit", "-r", "app", "-ll", "-q"],
    "tests+coverage": [
        "-m",
        "pytest",
        "-q",
        "--cov=app",
        f"--cov-fail-under={COVERAGE_MINIMUM}",
    ],
}
LOCK_SCHEMA_VERSION = 2


def sh(cmd: list[str]) -> dict[str, Any]:
    p = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {"exit_code": p.returncode, "stdout": p.stdout[-6000:], "stderr": p.stderr[-3000:]}


def gate(name: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"gate": name, "passed": passed, **detail}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traceability() -> dict[str, Any]:
    spec_ids = set(ID_PATTERN.findall(SPEC.read_text(encoding="utf-8")))
    test_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("*.py"))
    missing = sorted(spec_ids - set(ID_PATTERN.findall(test_text)))
    return gate("traceability", not missing, {
        "expected": f"every spec ID appears in tests ({len(spec_ids)} IDs)",
        "observed": f"missing from tests: {missing}" if missing else "all IDs referenced",
    })


def git_output(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def project_relative_git_paths() -> list[str]:
    prefix = git_output("rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        raise RuntimeError(f"Unable to determine Git path prefix: {prefix.stderr}")
    git_root_prefix = prefix.stdout.strip().replace("\\", "/")

    tracked = git_output("ls-files", "--full-name", "-z")
    if tracked.returncode != 0:
        raise RuntimeError(f"Unable to list tracked files: {tracked.stderr}")

    paths = []
    for path in tracked.stdout.split("\0"):
        normalized = path.replace("\\", "/")
        if normalized.startswith(git_root_prefix):
            paths.append(normalized[len(git_root_prefix) :])
    return paths


def protected_paths() -> list[Path]:
    source_files = sorted(
        path
        for folder in ("app", "tests")
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and path.suffix == ".py"
    )
    recorded_evidence = [
        path
        for folder in (
            "evidence/results",
            "evidence/final-generation",
            "evidence/initial-generation",
        )
        for path in (ROOT / folder).rglob("*")
        if path.is_file()
    ]
    return [
        RUFF_CONFIG,
        HARNESS / "run.py",
        PYPROJECT,
        SPEC,
        PLAN,
        TASKS,
        CONSTITUTION,
        *source_files,
        *recorded_evidence,
    ]


def protected_digest(path: Path) -> str:
    content = path.read_bytes()
    if path == TASKS:
        content = re.sub(rb"(?m)^(\s*-\s*)\[[ xX]\]", rb"\1[ ]", content)
    return hashlib.sha256(content).hexdigest()


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted_name(node.value)}.{node.attr}"
    return ""


def has_forbidden_suppression(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return any(
        token.type == tokenize.COMMENT and FORBIDDEN.search(token.string)
        for token in tokens
    )


def has_skipped_test(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip_aliases = {"pytest.skip"}
    mark_aliases = {"pytest.mark"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_name = alias.asname or alias.name
                    skip_aliases.add(f"{pytest_name}.skip")
                    mark_aliases.add(f"{pytest_name}.mark")
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "skip":
                    skip_aliases.add(alias.asname or alias.name)
                elif alias.name == "mark":
                    mark_aliases.add(alias.asname or alias.name)

    skip_decorators = {
        f"{mark_alias}.{skip_name}"
        for mark_alias in mark_aliases
        for skip_name in ("skip", "skipif", "xfail")
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if dotted_name(target) in skip_decorators:
                    return True
        if isinstance(node, ast.Call) and dotted_name(node.func) in skip_aliases:
            return True
    return False


def ruff_excludes_active_sources(patterns: list[str]) -> list[str]:
    excluded = []
    for folder in ("app", "tests", ".harness"):
        candidates = (folder, f"{folder}/__ruff_guardrail_probe__.py")
        for pattern in patterns:
            normalized = pattern.replace("\\", "/")
            variants = {normalized}
            while normalized.startswith("**/"):
                normalized = normalized[3:]
                variants.add(normalized)
            if any(
                fnmatch.fnmatchcase(candidate, variant)
                for candidate in candidates
                for variant in variants
            ):
                excluded.append(f"{folder} (matched by {pattern})")
                break
    return excluded


def secret_scan_contents(path: Path) -> list[str]:
    contents = [path.read_bytes().decode("latin-1")]
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            contents.extend(
                archive.read(info).decode("latin-1")
                for info in archive.infolist()
                if not info.is_dir()
            )
    return contents


def lock_contents() -> dict[str, Any]:
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "files": {
            path.relative_to(ROOT).as_posix(): protected_digest(path)
            for path in protected_paths()
        },
    }


def guardrails() -> dict[str, Any]:
    problems = []
    required_gates = {"syntax", "lint", "security", "tests+coverage"}
    if set(GATE_COMMANDS) != required_gates:
        problems.append(f"required gate commands must be exactly {sorted(required_gates)}")

    for folder in ("app", "tests", ".harness"):
        for f in (ROOT / folder).rglob("*.py"):
            if has_forbidden_suppression(f):
                problems.append(f"suppression comment in {f.relative_to(ROOT)}")

    for f in (ROOT / "tests").rglob("*.py"):
        if has_skipped_test(f):
            problems.append(f"test skip/xfail marker in {f.relative_to(ROOT)}")

    if COVERAGE_MINIMUM < 85:
        problems.append("coverage threshold is below 85%")
    for name, command in GATE_COMMANDS.items():
        if name == "syntax" and command != [
            "-m",
            "compileall",
            "-q",
            "app",
            "tests",
        ]:
            problems.append("syntax gate does not compile app and tests")
        if name == "lint" and command != [
            "-m",
            "ruff",
            "check",
            ".",
            "--config",
            ".harness/ruff.toml",
        ]:
            problems.append("Ruff gate command does not use the protected configuration")
        if name == "security" and not (
            command[:4] == ["-m", "bandit", "-r", "app"] and "-ll" in command
        ):
            problems.append("Bandit gate does not scan app at MEDIUM/HIGH severity")
        if name == "tests+coverage" and not (
            "--cov=app" in command
            and f"--cov-fail-under={COVERAGE_MINIMUM}" in command
        ):
            problems.append("pytest gate does not enforce app coverage threshold")

    if not LOCK.exists():
        problems.append("protected.sha256 missing")
    else:
        try:
            locked = json.loads(LOCK.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"protected file manifest is invalid JSON: {error}")
        else:
            if not isinstance(locked, dict) or not isinstance(locked.get("files"), dict):
                problems.append("protected file manifest has an invalid structure")
            else:
                actual = lock_contents()
                if locked != actual:
                    locked_files = locked["files"]
                    actual_files = actual["files"]
                    missing = sorted(set(locked_files) - set(actual_files))
                    added = sorted(set(actual_files) - set(locked_files))
                    changed = sorted(
                        path
                        for path in set(locked_files) & set(actual_files)
                        if locked_files[path] != actual_files[path]
                    )
                    if missing:
                        problems.append(f"protected files missing: {missing}")
                    if added:
                        problems.append(f"unreviewed protected files added: {added}")
                    if changed:
                        problems.append(f"protected files changed: {changed}")
                    if locked.get("schema_version") != LOCK_SCHEMA_VERSION:
                        problems.append("protected file manifest has an unsupported schema")

    tracked_paths = project_relative_git_paths()
    listed_paths = git_output(
        "ls-files", "--full-name", "-co", "--exclude-standard", "-z"
    )
    if listed_paths.returncode != 0:
        problems.append(f"unable to list committed and untracked files: {listed_paths.stderr}")
        candidate_paths = tracked_paths
    else:
        prefix = git_output("rev-parse", "--show-prefix").stdout.strip().replace("\\", "/")
        candidate_paths = [
            path.replace("\\", "/")[len(prefix) :]
            for path in listed_paths.stdout.split("\0")
            if path.replace("\\", "/").startswith(prefix)
        ]

    env_files = sorted(
        path
        for path in candidate_paths
        if re.search(r"(^|/)\.env(?:$|\.)", path, re.IGNORECASE)
    )
    if env_files:
        problems.append(f"environment files must not be committed: {env_files}")

    secrets = []
    for relative_path in candidate_paths:
        path = ROOT / relative_path
        if not path.is_file():
            continue
        contents = secret_scan_contents(path)
        if any(
            pattern.search(content)
            for pattern in SECRET_PATTERNS
            for content in contents
        ):
            secrets.append(relative_path)
    if secrets:
        problems.append(f"possible secrets found in repository files: {sorted(secrets)}")

    result_diff = git_output(
        "diff",
        "--quiet",
        "HEAD",
        "--",
        "evidence/results",
        "evidence/final-generation",
        "evidence/initial-generation",
    )
    if result_diff.returncode == 1:
        problems.append("tracked evidence/results files were modified or deleted")
    elif result_diff.returncode != 0:
        problems.append(f"unable to verify recorded-result integrity: {result_diff.stderr}")

    ruff_config = tomllib.loads(RUFF_CONFIG.read_text(encoding="utf-8"))
    exclusions = []
    for key in ("exclude", "extend-exclude"):
        patterns = ruff_config.get(key, [])
        if not isinstance(patterns, list) or not all(
            isinstance(pattern, str) for pattern in patterns
        ):
            problems.append(f"Ruff {key} must be a list of path patterns")
        else:
            exclusions.extend(patterns)
    problems.extend(
        f"Ruff excludes active source {path}"
        for path in ruff_excludes_active_sources(exclusions)
    )

    return gate("guardrails", not problems, {
        "expected": (
            "no suppression/skip markers; unchanged tests/spec/config; unchanged "
            "recorded results; no tracked secrets/.env; required gate thresholds"
        ),
        "observed": problems or "ok",
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label")
    ap.add_argument("--lock", action="store_true")
    args = ap.parse_args()
    if args.lock:
        existing = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
        actual = lock_contents()
        if existing and set(existing) == {"ruff.toml"}:
            if existing["ruff.toml"] != digest(RUFF_CONFIG):
                raise SystemExit(
                    "Existing Ruff configuration hash does not match; refusing to lock."
                )
        elif existing:
            old_files = existing.get("files", {})
            actual_files = actual["files"]
            removed = set(old_files) - set(actual_files)
            changed = {
                path
                for path in set(old_files) & set(actual_files)
                if old_files[path] != actual_files[path]
            }
            added = set(actual_files) - set(old_files)
            allowed_baseline_additions = {
                ".specify/memory/constitution.md",
                "specs/001-smart-todo/plan.md",
            }
            allowed_baseline_changes = {".harness/run.py"}
            if (
                existing.get("schema_version") != LOCK_SCHEMA_VERSION
                or any(
                    not path.startswith("evidence/")
                    and path not in allowed_baseline_additions
                    for path in added
                )
                or any("__pycache__" not in path and not path.endswith(".pyc") for path in removed)
                or changed - allowed_baseline_changes
            ):
                raise SystemExit(
                    "Protected baseline has unexpected changes; refusing to replace it."
                )
        LOCK.write_text(json.dumps(actual, indent=2), encoding="utf-8")
        print("Locked protected source/spec baseline:", LOCK)
        return 0
    if not args.label:
        raise SystemExit("--label is required")

    py = sys.executable
    gates = []
    for name, command_args in GATE_COMMANDS.items():
        cmd = [py, *command_args]
        r = sh(cmd)
        gates.append(gate(name, r["exit_code"] == 0, {"command": " ".join(cmd[1:]), **r}))
    gates += [traceability(), guardrails()]

    overall = all(g["passed"] for g in gates)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {
        "label": args.label,
        "captured_at": stamp,
        "overall": "PASS" if overall else "FAIL",
        "gates": gates,
    }
    out = RESULTS / f"harness-{args.label}-{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for g in gates:
        print(f"{'PASS' if g['passed'] else 'FAIL'}  {g['gate']}")
    print(f"OVERALL: {report['overall']}  ->  {out.relative_to(ROOT)}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())