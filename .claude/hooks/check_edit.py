#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit): 파일이 바뀔 때마다 자동 검사.

1. 스택 감지: 수정된 파일에서 위로 올라가며 가장 가까운 pyproject.toml / package.json 을 찾는다.
2. 스택별 검사
   - Python: ruff format(자동 교정) -> ruff check
   - JS/TS : prettier --write(자동 교정) -> eslint   (프로젝트에 설치되어 있을 때)
   - JSON  : 파싱, Shell: bash -n
3. 공통 규칙: 비밀값, 파일 길이, 금지 패턴(TODO 형식, 검사 끄기 주석 등)

문제가 있으면 exit 2 + stderr 로 에이전트에게 피드백 -> 에이전트가 스스로 고치는 루프.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from _lib import (
    PASS,
    feedback,
    file_path_of,
    harness_root,
    load_config,
    log_event,
    matches_name,
    read_event,
    rel_path,
    role_of,
)

TIMEOUT = 90
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh"}
JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
SKIP_PARTS = {"node_modules", ".venv", "venv", "dist", "build", ".harness", "__pycache__"}


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 0, f"(검사 도구 실행 실패, 건너뜀: {exc})"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def component_root(path: Path, marker: str) -> Path | None:
    """path 에서 위로 올라가며 marker 파일이 있는 폴더를 찾는다 (하네스 루트까지)."""
    root = harness_root()
    for parent in path.parents:
        if (parent / marker).exists():
            return parent
        if parent == root:
            break
    return None


def check_python(path: Path) -> list[str]:
    if not shutil.which("ruff"):
        code, out = run([sys.executable, "-m", "py_compile", str(path)], path.parent)
        return [f"문법 오류: {out}"] if code else []
    cwd = component_root(path, "pyproject.toml") or path.parent
    run(["ruff", "format", "--quiet", str(path)], cwd)
    code, out = run(["ruff", "check", "--output-format", "concise", str(path)], cwd)
    if code == 0:
        return []
    return [line for line in out.splitlines() if line and not line.startswith(("Found", "["))]


def check_js(path: Path) -> list[str]:
    cwd = component_root(path, "package.json")
    if cwd is None:
        return []
    bin_dir = cwd / "node_modules" / ".bin"
    if (bin_dir / "prettier").exists():
        run([str(bin_dir / "prettier"), "--write", "--log-level", "warn", str(path)], cwd)
    if not (bin_dir / "eslint").exists():
        return []
    code, out = run([str(bin_dir / "eslint"), "--format", "unix", str(path)], cwd)
    if code == 0:
        return []
    return [line for line in out.splitlines() if line and "problem" not in line]


def check_json(path: Path) -> list[str]:
    if path.name.startswith("tsconfig"):
        return []  # tsconfig 는 주석을 허용하는 JSONC
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"JSON 파싱 오류: {exc}"]
    return []


def check_shell(path: Path) -> list[str]:
    code, out = run(["bash", "-n", str(path)], path.parent)
    return [f"bash 문법 오류: {out}"] if code else []


def check_rules(rel: str, text: str, cfg: dict) -> list[str]:
    rules = cfg.get("edit_checks", {})
    issues: list[str] = []
    lines = text.splitlines()
    max_lines = rules.get("max_file_lines", 0)
    if max_lines and len(lines) > max_lines and Path(rel).suffix in CODE_SUFFIXES:
        issues.append(f"{rel}: {len(lines)}줄입니다 (최대 {max_lines}). 모듈을 나누세요.")
    for no, line in enumerate(lines, 1):
        for rule in rules.get("secret_patterns", []):
            if re.search(rule["pattern"], line):
                issues.append(f"{rel}:{no} 비밀값 의심({rule['name']}). 환경변수로 옮기세요.")
        for rule in rules.get("line_rules", []):
            if matches_name(rel, [rule["glob"]]) and re.search(rule["pattern"], line):
                issues.append(f"{rel}:{no} {rule['message']}")
    return issues


def collect_issues(path: Path, rel: str, cfg: dict) -> list[str]:
    issues: list[str] = []
    if path.suffix == ".py":
        issues += check_python(path)
    elif path.suffix in JS_SUFFIXES:
        issues += check_js(path)
    elif path.suffix == ".json":
        issues += check_json(path)
    elif path.suffix == ".sh":
        issues += check_shell(path)
    with contextlib.suppress(UnicodeDecodeError, OSError):
        issues += check_rules(rel, path.read_text(encoding="utf-8"), cfg)
    return issues


def main() -> int:
    event = read_event()
    file_path = file_path_of(event)
    if not file_path:
        return PASS
    rel = rel_path(file_path)
    path = Path(file_path)
    if rel is None or not path.is_file() or SKIP_PARTS & set(Path(rel).parts):
        return PASS

    cfg = load_config()
    issues = collect_issues(path, rel, cfg)
    role = role_of(event)
    log_event(
        "check_edit",
        "fail" if issues else "pass",
        role=role,
        file=rel,
        issues=len(issues),
        details=issues[:20],
    )
    if not issues:
        return PASS
    limit = cfg.get("edit_checks", {}).get("max_feedback_lines", 25)
    return feedback(
        f"{rel} 자동 검사에서 {len(issues)}건의 문제가 발견되었습니다.",
        issues[:limit],
        "다음 작업으로 넘어가기 전에 모두 고치세요. 검사를 끄거나 우회하지 마세요.",
    )


if __name__ == "__main__":
    sys.exit(main())
