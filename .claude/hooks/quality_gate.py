#!/usr/bin/env python3
"""Stop / SubagentStop: 품질 게이트.

에이전트가 "끝났다"고 멈추려는 순간 변경된 프로젝트 전체를 검사한다.
실패하면 exit 2로 멈춤을 거부하고 실패 내용을 피드백한다 -> 에이전트가 계속 고친다.

- 검사 대상: 변경 사항이 있는 workplace/<프로젝트> (프로젝트별 git 기준)
- 검사 명령: 프로젝트에 Makefile `check` 타깃이 있으면 `make check`,
  없으면 스택 자동 감지 (Python: ruff + pytest / Node: package.json의 lint·typecheck·test 스크립트)
- SubagentStop은 코드를 쓰는 역할(quality_gate.subagent_roles)에만 적용한다.
- 무한 루프 방지: 같은 역할이 연속 max_retries 번 실패하면 멈춤을 허용하고 사람에게 넘긴다.
- 하네스 자체(.claude/hooks, tests)가 바뀌었으면 하네스 테스트도 돌린다.
- 변조 감지: 관리자 모드가 아닌데 보호 파일이 바뀌었으면 한 번 멈추고 보고하게 한다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from _lib import (
    PASS,
    feedback,
    harness_root,
    is_admin,
    load_config,
    log_event,
    matches,
    read_event,
    role_of,
)

TAIL = 30


def run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, f"{timeout}초 안에 끝나지 않았습니다."
    except OSError as exc:
        return 0, f"(실행 실패, 건너뜀: {exc})"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def git_changes(cwd: Path) -> list[str] | None:
    """변경·추가된 파일 목록. git 저장소가 아니면 None."""
    if not (cwd / ".git").exists():
        return None
    code, out = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd, 30)
    if code != 0:
        return None
    return [line[3:].split(" -> ")[-1].strip('"') for line in out.splitlines() if line]


def changed_projects() -> list[Path]:
    workplace = harness_root() / "workplace"
    if not workplace.is_dir():
        return []
    projects = []
    for project in sorted(p for p in workplace.iterdir() if p.is_dir()):
        changes = git_changes(project)
        if changes is None or changes:
            projects.append(project)
    return projects


def has_make_target(cwd: Path, target: str) -> bool:
    if not (cwd / "Makefile").exists() or not shutil.which("make"):
        return False
    code, _ = run(["make", "-n", target], cwd, 30)
    return code == 0


def auto_checks(project: Path) -> list[tuple[str, list[str], Path, tuple[int, ...]]]:
    """Makefile이 없을 때 스택을 감지해 검사 목록을 만든다."""
    checks = []
    components = [project] + [p for p in project.iterdir() if p.is_dir()]
    for comp in components:
        if (comp / "pyproject.toml").exists() and shutil.which("ruff"):
            checks.append(("ruff check", ["ruff", "check", "."], comp, (0,)))
            checks.append(("ruff format", ["ruff", "format", "--check", "."], comp, (0,)))
            pytest = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header"]
            checks.append(("pytest", pytest, comp, (0, 5)))
        package = comp / "package.json"
        if package.exists() and (comp / "node_modules").exists() and shutil.which("npm"):
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            for name in ("lint", "typecheck", "test"):
                if name in scripts:
                    checks.append((f"npm {name}", ["npm", "run", "--silent", name], comp, (0,)))
    return checks


def check_project(project: Path, timeout: int) -> list[str]:
    if has_make_target(project, "check"):
        checks = [("make check", ["make", "check"], project, (0,))]
    else:
        checks = auto_checks(project)
    failures = []
    for name, cmd, cwd, ok_codes in checks:
        code, out = run(cmd, cwd, timeout)
        if code not in ok_codes:
            tail = "\n".join(f"      {line}" for line in out.splitlines()[-TAIL:])
            where = cwd.relative_to(harness_root()).as_posix()
            failures.append(f"{where}: {name} 실패 (exit {code})\n{tail}")
    return failures


def check_harness(changes: list[str], timeout: int) -> list[str]:
    if not any(c.startswith((".claude/hooks/", "tests/")) for c in changes):
        return []
    code, out = run([sys.executable, "-m", "pytest", "-q", "tests"], harness_root(), timeout)
    if code in (0, 5):
        return []
    tail = "\n".join(f"      {line}" for line in out.splitlines()[-TAIL:])
    return [f"하네스 테스트 실패 (exit {code})\n{tail}"]


def state_path(name: str) -> Path:
    path = harness_root() / ".harness" / "state" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def bump_failures(role: str, reset: bool = False) -> int:
    path = state_path(f"gate_failures_{role}")
    try:
        count = 0 if reset else int(path.read_text().strip()) + 1
    except (OSError, ValueError):
        count = 1
    path.write_text(str(count))
    return count


def tamper_once(tampered: list[str]) -> bool:
    path = state_path("tamper_reported")
    key = "\n".join(sorted(tampered))
    if path.exists() and path.read_text() == key:
        return False
    path.write_text(key)
    return True


def notify_gave_up(names: list[str], failures: list[str], max_retries: int) -> None:
    """에이전트가 스스로 해결하지 못한 상태 -> 대표에게 메일."""
    try:
        from notify import send
    except ImportError:
        return
    body = "\n".join(
        [
            f"품질 게이트가 {max_retries}회 연속 실패해 에이전트가 더 진행하지 못합니다.",
            f"프로젝트: {', '.join(names) or '-'}",
            "",
            "실패 내용 (앞부분):",
            *(f[:800] for f in failures[:3]),
        ]
    )
    send("품질 게이트 중단: 사람의 확인 필요", body, kind="gave_up")


def main() -> int:
    event = read_event()
    hook = event.get("hook_event_name", "Stop")
    role = role_of(event)
    cfg = load_config()
    gate = cfg.get("quality_gate", {})
    if hook == "SubagentStop" and role not in gate.get("subagent_roles", []):
        return PASS

    root_changes = git_changes(harness_root()) or []
    tampered = [c for c in root_changes if matches(c, cfg.get("protected_paths", []))]
    if tampered and not is_admin(cfg) and tamper_once(tampered):
        log_event("quality_gate", "tamper_warning", role=role, files=tampered)
        return feedback(
            "보호된 하네스 파일이 바뀌었습니다.",
            tampered,
            "에이전트는 이 파일을 수정하면 안 됩니다. 누가 왜 바꿨는지 사용자에게 보고하세요.",
        )

    timeout = gate.get("timeout_sec", 600)
    failures = check_harness(root_changes, timeout)
    projects = changed_projects()
    for project in projects:
        failures += check_project(project, timeout)

    names = [p.name for p in projects]
    if not failures:
        bump_failures(role, reset=True)
        if names:
            log_event("quality_gate", "pass", role=role, event=hook, projects=names)
        return PASS

    count = bump_failures(role)
    max_retries = gate.get("max_retries", 3)
    if count > max_retries:
        bump_failures(role, reset=True)
        log_event("quality_gate", "gave_up", role=role, event=hook, projects=names)
        notify_gave_up(names, failures, max_retries)
        message = (
            f"[HARNESS] 품질 게이트가 {max_retries}회 연속 실패했습니다. 사람의 확인이 필요합니다."
        )
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        return PASS

    log_event("quality_gate", "fail", role=role, event=hook, attempt=count, projects=names)
    return feedback(
        f"품질 게이트 실패 ({count}/{max_retries}). 아직 끝낼 수 없습니다.",
        failures,
        "원인을 고치세요. 테스트를 지우거나 skip하거나 검사를 우회하지 마세요. "
        "PM이라면 담당 에이전트에게 수정을 맡기세요.",
    )


if __name__ == "__main__":
    sys.exit(main())
