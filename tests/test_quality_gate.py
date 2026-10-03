"""품질 게이트(quality_gate) 테스트."""

from __future__ import annotations

from conftest import Harness

P = "workplace/demo"
PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def make_project(harness: Harness, test_body: str) -> None:
    harness.git_init(P)
    harness.write(f"{P}/pyproject.toml", PYPROJECT)
    harness.write(f"{P}/tests/unit/test_x.py", test_body)


def stop(role: str | None = None, hook: str = "Stop") -> dict:
    event: dict = {"hook_event_name": hook}
    if role:
        event["agent_type"] = role
    return event


FAILING = "def test_fail() -> None:\n    assert 1 == 2\n"
PASSING = "def test_ok() -> None:\n    assert 1 == 1\n"


def test_failing_project_blocks_then_gives_up(harness: Harness) -> None:
    make_project(harness, FAILING)
    for attempt in range(1, 4):
        result = harness.run("quality_gate.py", stop())
        assert result.returncode == 2
        assert f"({attempt}/3)" in result.stderr
    result = harness.run("quality_gate.py", stop())
    assert result.returncode == 0
    assert "사람의 확인" in result.stdout


def test_passing_project_is_allowed(harness: Harness) -> None:
    make_project(harness, PASSING)
    result = harness.run("quality_gate.py", stop())
    assert result.returncode == 0, result.stderr


def test_gate_applies_to_developer_subagent(harness: Harness) -> None:
    make_project(harness, FAILING)
    result = harness.run("quality_gate.py", stop("developer", "SubagentStop"))
    assert result.returncode == 2


def test_gate_skips_read_only_subagents(harness: Harness) -> None:
    make_project(harness, FAILING)
    result = harness.run("quality_gate.py", stop("reviewer", "SubagentStop"))
    assert result.returncode == 0


def test_makefile_check_target_is_preferred(harness: Harness) -> None:
    harness.git_init(P)
    harness.write(f"{P}/Makefile", "check:\n\t@echo custom-check && exit 1\n")
    result = harness.run("quality_gate.py", stop())
    assert result.returncode == 2
    assert "make check" in result.stderr
    assert "custom-check" in result.stderr


def test_clean_project_is_not_checked(harness: Harness) -> None:
    make_project(harness, FAILING)
    cwd = harness.root / P
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=cwd, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
        cwd=cwd,
        check=True,
    )
    result = harness.run("quality_gate.py", stop())
    assert result.returncode == 0


def test_tampering_is_reported_once(harness: Harness) -> None:
    harness.git_init()
    harness.write("CLAUDE.md", "changed by an agent\n")
    first = harness.run("quality_gate.py", stop())
    assert first.returncode == 2
    assert "CLAUDE.md" in first.stderr
    second = harness.run("quality_gate.py", stop())
    assert second.returncode == 0


def test_admin_changes_are_not_tampering(harness: Harness) -> None:
    harness.admin_on()
    harness.git_init()
    harness.write("CLAUDE.md", "changed by the owner\n")
    result = harness.run("quality_gate.py", stop())
    assert result.returncode == 0
