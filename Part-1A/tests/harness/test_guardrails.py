import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest

HARNESS_PATH = Path(__file__).resolve().parents[2] / ".harness" / "run.py"
HARNESS_SPEC = importlib.util.spec_from_file_location("part1a_harness", HARNESS_PATH)
assert HARNESS_SPEC is not None
assert HARNESS_SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(HARNESS_SPEC)
HARNESS_SPEC.loader.exec_module(HARNESS)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    files = {
        ".harness/run.py": "print('harness')\n",
        ".harness/ruff.toml": (
            'line-length = 100\nextend-exclude = ["evidence", "specs", ".venv"]\n'
        ),
        "pyproject.toml": "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        "specs/001-smart-todo/spec.md": "FR-001\nNFR-001\n",
        "specs/001-smart-todo/plan.md": "Python 3.13\n",
        "specs/001-smart-todo/tasks.md": "- [x] T001 Example task\n",
        ".specify/memory/constitution.md": "Version 1.1.0\n",
        "app/main.py": "VALUE = 1\n",
        "tests/test_sample.py": "def test_sample():\n    assert True\n",
        "evidence/results/historical.json": '{"overall": "PASS"}\n',
        "evidence/initial-generation/source.py": "VALUE = 1\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    snapshot = tmp_path / "evidence/final-generation/old.zip"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(snapshot, "w") as archive:
        archive.writestr("source.py", "VALUE = 1\n")

    files["evidence/final-generation/old.zip"] = "snapshot"
    tracked_paths = list(files)
    state: dict[str, Any] = {
        "candidate_paths": list(files),
        "result_diff": 0,
    }
    monkeypatch.setattr(HARNESS, "ROOT", tmp_path)
    monkeypatch.setattr(HARNESS, "HARNESS", tmp_path / ".harness")
    monkeypatch.setattr(HARNESS, "LOCK", tmp_path / ".harness" / "protected.sha256")
    monkeypatch.setattr(HARNESS, "RUFF_CONFIG", tmp_path / ".harness" / "ruff.toml")
    monkeypatch.setattr(HARNESS, "PYPROJECT", tmp_path / "pyproject.toml")
    monkeypatch.setattr(HARNESS, "SPEC", tmp_path / "specs/001-smart-todo/spec.md")
    monkeypatch.setattr(HARNESS, "PLAN", tmp_path / "specs/001-smart-todo/plan.md")
    monkeypatch.setattr(HARNESS, "TASKS", tmp_path / "specs/001-smart-todo/tasks.md")
    monkeypatch.setattr(
        HARNESS,
        "CONSTITUTION",
        tmp_path / ".specify/memory/constitution.md",
    )
    monkeypatch.setattr(HARNESS, "__file__", str(tmp_path / ".harness" / "run.py"))
    monkeypatch.setattr(HARNESS, "project_relative_git_paths", lambda: tracked_paths)

    def fake_git_output(*args: str) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("rev-parse", "--show-prefix"):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args and args[0] == "ls-files":
            output = "\0".join(state["candidate_paths"])
            return subprocess.CompletedProcess(args, 0, output, "")
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(args, state["result_diff"], "", "")
        raise AssertionError(f"Unexpected Git command: {args}")

    monkeypatch.setattr(HARNESS, "git_output", fake_git_output)
    HARNESS.LOCK.write_text(json.dumps(HARNESS.lock_contents(), indent=2), encoding="utf-8")
    return {"root": tmp_path, "state": state, "tracked_paths": tracked_paths}


def problems(workspace: dict[str, Any]) -> list[str]:
    result = HARNESS.guardrails()
    assert not result["passed"]
    assert isinstance(result["observed"], list)
    return result["observed"]


def test_clean_workspace_passes_all_guardrail_checks(workspace: dict[str, Any]) -> None:
    """A valid protected workspace is accepted by the guardrail evaluator."""
    assert HARNESS.guardrails()["passed"]


@pytest.mark.parametrize(
    ("relative_path", "content", "message"),
    [
        ("app/main.py", "VALUE = 1  # noqa: E501\n", "suppression comment"),
        ("app/main.py", "VALUE = 1  # nosec\n", "suppression comment"),
        (".harness/run.py", "VALUE = 1  # noqa\n", "suppression comment"),
        (
            "tests/test_sample.py",
            "@pytest.mark.skip\ndef test_sample(): pass\n",
            "test skip/xfail",
        ),
        (
            "tests/test_sample.py",
            "@pytest.mark.xfail\ndef test_sample(): pass\n",
            "test skip/xfail",
        ),
        ("tests/test_sample.py", "pytest.skip('not ready')\n", "test skip/xfail"),
        (
            "tests/test_sample.py",
            "from pytest import skip as skip_test\nskip_test()\n",
            "test skip/xfail",
        ),
    ],
)
def test_suppression_and_skip_markers_fail_guardrails(
    workspace: dict[str, Any],
    relative_path: str,
    content: str,
    message: str,
) -> None:
    target = workspace["root"] / relative_path
    target.write_text(content, encoding="utf-8")

    assert any(message in problem for problem in problems(workspace))


def test_changed_contract_test_fails_protected_baseline(workspace: dict[str, Any]) -> None:
    target = workspace["root"] / "tests/test_sample.py"
    target.write_text("def test_sample():\n    assert False\n", encoding="utf-8")

    assert any(
        "protected files changed" in problem and "tests/test_sample.py" in problem
        for problem in problems(workspace)
    )


def test_changed_acceptance_criteria_fail_protected_baseline(workspace: dict[str, Any]) -> None:
    target = workspace["root"] / "specs/001-smart-todo/spec.md"
    target.write_text("FR-001 removed\n", encoding="utf-8")

    assert any(
        "protected files changed" in problem and "spec.md" in problem
        for problem in problems(workspace)
    )


def test_changed_constitution_or_plan_fail_protected_baseline(
    workspace: dict[str, Any],
) -> None:
    plan = workspace["root"] / "specs/001-smart-todo/plan.md"
    plan.write_text("Changed plan\n", encoding="utf-8")

    assert any(
        "protected files changed" in problem and "plan.md" in problem
        for problem in problems(workspace)
    )


def test_changed_constitution_fails_protected_baseline(
    workspace: dict[str, Any],
) -> None:
    constitution = workspace["root"] / ".specify/memory/constitution.md"
    constitution.write_text("Version 1.0.0\n", encoding="utf-8")

    assert any(
        "protected files changed" in problem and "constitution.md" in problem
        for problem in problems(workspace)
    )


def test_added_test_fails_protected_baseline(workspace: dict[str, Any]) -> None:
    target = workspace["root"] / "tests/test_unreviewed.py"
    target.write_text("def test_unreviewed():\n    assert True\n", encoding="utf-8")

    assert any("unreviewed protected files added" in problem for problem in problems(workspace))


def test_lowered_coverage_threshold_fails_guardrails(
    workspace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(HARNESS, "COVERAGE_MINIMUM", 84)

    observed = problems(workspace)
    assert any("coverage threshold is below 85%" in problem for problem in observed)
    assert any(
        "pytest gate does not enforce app coverage threshold" in problem
        for problem in observed
    )


@pytest.mark.parametrize(
    ("gate_name", "command", "message"),
    [
        ("syntax", ["-m", "compileall", "-q"], "syntax gate"),
        ("lint", ["-m", "ruff", "check", "."], "Ruff gate command"),
        ("security", ["-m", "bandit", "-r", "app"], "Bandit gate"),
        ("tests+coverage", ["-m", "pytest", "-q"], "pytest gate"),
    ],
)
def test_weakened_quality_gate_command_fails_guardrails(
    workspace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    gate_name: str,
    command: list[str],
    message: str,
) -> None:
    commands = dict(HARNESS.GATE_COMMANDS)
    commands[gate_name] = command
    monkeypatch.setattr(HARNESS, "GATE_COMMANDS", commands)

    assert any(message in problem for problem in problems(workspace))


def test_missing_quality_gate_fails_guardrails(
    workspace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = dict(HARNESS.GATE_COMMANDS)
    del commands["security"]
    monkeypatch.setattr(HARNESS, "GATE_COMMANDS", commands)

    assert any("required gate commands" in problem for problem in problems(workspace))


@pytest.mark.parametrize("pattern", ["app/**", "**/tests/**", ".harness"])
def test_ruff_exclusion_of_active_source_fails_guardrails(
    workspace: dict[str, Any],
    pattern: str,
) -> None:
    config = workspace["root"] / ".harness/ruff.toml"
    config.write_text(
        f'line-length = 100\nextend-exclude = ["{pattern}"]\n',
        encoding="utf-8",
    )

    assert any("Ruff excludes active source" in problem for problem in problems(workspace))


@pytest.mark.parametrize(
    "secret",
    [
        "AKIA" + "ABCDEFGHIJKLMNOP",
        "ghp_" + "abcdefghijklmnopqrstuvwxyz123456",
        "password = " + "'a-very-long-secret-value-that-should-be-caught'",
        "-----BEGIN RSA " + "PRIVATE KEY-----",
    ],
)
def test_committed_secret_patterns_fail_guardrails(
    workspace: dict[str, Any],
    secret: str,
) -> None:
    candidate = "app/credentials.py"
    target = workspace["root"] / candidate
    target.write_text(f"CREDENTIAL = {secret!r}\n", encoding="utf-8")
    workspace["state"]["candidate_paths"].append(candidate)

    assert any("possible secrets found" in problem for problem in problems(workspace))


def test_secret_in_final_snapshot_archive_fails_guardrails(
    workspace: dict[str, Any],
) -> None:
    snapshot = workspace["root"] / "evidence/final-generation/old.zip"
    with zipfile.ZipFile(snapshot, "w") as archive:
        archive.writestr(
            "credentials.py",
            "TOKEN = 'AKIA" + "ABCDEFGHIJKLMNOP'\n",
        )

    assert any("possible secrets found" in problem for problem in problems(workspace))


@pytest.mark.parametrize("env_path", [".env", ".env.production", "config/.ENV.local"])
def test_committed_environment_files_fail_guardrails(
    workspace: dict[str, Any],
    env_path: str,
) -> None:
    workspace["state"]["candidate_paths"].append(env_path)

    assert any(
        "environment files must not be committed" in problem
        for problem in problems(workspace)
    )


def test_changed_historical_report_fails_protected_result_check(
    workspace: dict[str, Any],
) -> None:
    report = workspace["root"] / "evidence/results/historical.json"
    report.write_text('{"overall": "FAIL"}\n', encoding="utf-8")

    assert any(
        "protected files changed" in problem and "evidence/results/historical.json" in problem
        for problem in problems(workspace)
    )


def test_git_diff_of_recorded_results_fails_guardrails(
    workspace: dict[str, Any],
) -> None:
    workspace["state"]["result_diff"] = 1

    assert any(
        "tracked evidence/results files were modified or deleted" in problem
        for problem in problems(workspace)
    )


def test_tracked_evidence_files_are_in_protected_manifest(
    workspace: dict[str, Any],
) -> None:
    manifest = json.loads(HARNESS.LOCK.read_text(encoding="utf-8"))

    assert "evidence/results/historical.json" in manifest["files"]
    assert "evidence/final-generation/old.zip" in manifest["files"]
    assert "evidence/initial-generation/source.py" in manifest["files"]
    assert ".specify/memory/constitution.md" in manifest["files"]
    assert "specs/001-smart-todo/plan.md" in manifest["files"]


@pytest.mark.parametrize("manifest_text", ["{invalid", '{"files": []}'])
def test_invalid_protected_manifest_fails_guardrails(
    workspace: dict[str, Any],
    manifest_text: str,
) -> None:
    HARNESS.LOCK.write_text(manifest_text, encoding="utf-8")

    observed = problems(workspace)
    assert any("protected file manifest" in problem for problem in observed)


@pytest.mark.parametrize(
    "relative_path",
    [
        ".harness/ruff.toml",
        ".specify/memory/constitution.md",
        "app/main.py",
        "evidence/results/historical.json",
        "specs/001-smart-todo/spec.md",
        "tests/test_sample.py",
    ],
)
def test_lock_refuses_to_rebaseline_protected_changes(
    workspace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    lock_before = HARNESS.LOCK.read_bytes()
    target = workspace["root"] / relative_path
    target.write_text(target.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    monkeypatch.setattr(HARNESS.sys, "argv", ["run.py", "--lock"])

    with pytest.raises(SystemExit, match="unexpected changes"):
        HARNESS.main()

    assert HARNESS.LOCK.read_bytes() == lock_before


def test_lock_refuses_unreviewed_test_addition(
    workspace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unreviewed_test = workspace["root"] / "tests/test_unreviewed.py"
    unreviewed_test.write_text("def test_unreviewed():\n    assert True\n", encoding="utf-8")
    lock_before = HARNESS.LOCK.read_bytes()
    monkeypatch.setattr(HARNESS.sys, "argv", ["run.py", "--lock"])

    with pytest.raises(SystemExit, match="unexpected changes"):
        HARNESS.main()

    assert HARNESS.LOCK.read_bytes() == lock_before


def test_deleted_historical_snapshot_fails_protected_baseline(
    workspace: dict[str, Any],
) -> None:
    (workspace["root"] / "evidence/final-generation/old.zip").unlink()

    assert any(
        "protected files missing" in problem
        and "evidence/final-generation/old.zip" in problem
        for problem in problems(workspace)
    )


def test_marker_examples_in_strings_are_not_violations(
    workspace: dict[str, Any],
) -> None:
    (workspace["root"] / "app/main.py").write_text(
        'COMMENT_EXAMPLES = "# noqa # nosec"\n',
        encoding="utf-8",
    )
    marker_example = "@pytest.mark.skip\npytest.skip('example')"
    (workspace["root"] / "tests/test_sample.py").write_text(
        f"MARKER_EXAMPLE = {marker_example!r}\n",
        encoding="utf-8",
    )
    HARNESS.LOCK.write_text(json.dumps(HARNESS.lock_contents(), indent=2), encoding="utf-8")

    assert HARNESS.guardrails()["passed"]


def test_git_paths_are_normalized_from_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git_output(*args: str) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("rev-parse", "--show-prefix"):
            return subprocess.CompletedProcess(args, 0, "Part-1A/\n", "")
        if args and args[0] == "ls-files":
            assert "--full-name" in args
            return subprocess.CompletedProcess(
                args,
                0,
                "Part-1A/evidence/results/human-review.json\0"
                "Part-1A/app/main.py\0",
                "",
            )
        raise AssertionError(f"Unexpected Git command: {args}")

    monkeypatch.setattr(HARNESS, "git_output", fake_git_output)

    assert HARNESS.project_relative_git_paths() == [
        "evidence/results/human-review.json",
        "app/main.py",
    ]


def test_traceability_fails_when_a_spec_identifier_has_no_test(
    workspace: dict[str, Any],
) -> None:
    result = HARNESS.traceability()

    assert not result["passed"]
    assert result["observed"] == "missing from tests: ['FR-001', 'NFR-001']"


def test_traceability_passes_when_every_spec_identifier_is_tested(
    workspace: dict[str, Any],
) -> None:
    test_file = workspace["root"] / "tests/test_sample.py"
    test_file.write_text(
        '"""FR-001 and NFR-001 have executable test coverage."""\n'
        "def test_requirements():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    result = HARNESS.traceability()

    assert result["passed"]
    assert result["observed"] == "all IDs referenced"
