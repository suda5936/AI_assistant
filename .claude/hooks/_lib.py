"""하네스 훅 공통 모듈.

Claude Code는 훅 스크립트의 stdin으로 이벤트 JSON을 넘긴다.
- 서브에이전트가 부른 도구라면 `agent_type`(예: "developer")이 들어 있다.
- 메인 세션(PM)이 부른 도구라면 `agent_type`이 없다 -> 역할 "main".

종료 코드 규약:
  0 -> 통과
  2 -> 차단 또는 피드백. stderr 내용이 에이전트에게 전달된다.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time
from pathlib import Path

PASS = 0
BLOCK = 2


def harness_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def load_config() -> dict:
    path = harness_root() / ".claude" / "harness.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_event() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def role_of(event: dict) -> str:
    return event.get("agent_type") or "main"


def is_admin(cfg: dict) -> bool:
    flag = cfg.get("admin_flag")
    return bool(flag) and Path(os.path.expanduser(flag)).exists()


def rel_path(file_path: str) -> str | None:
    """하네스 루트 기준 상대 경로. 루트 밖이면 None."""
    path = Path(file_path)
    if not path.is_absolute():
        path = harness_root() / path
    try:
        return path.resolve().relative_to(harness_root()).as_posix()
    except ValueError:
        return None


def matches(path: str, globs: list[str]) -> bool:
    """경로 전체 기준 glob 매칭. '*'는 '/'도 포함한다."""
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def matches_name(path: str, globs: list[str]) -> bool:
    """파일 이름 기준 glob 매칭 (비밀 파일 판별용)."""
    name = Path(path).name
    return any(fnmatch.fnmatchcase(name, g) for g in globs)


def project_of(rel: str) -> str | None:
    """'workplace/<프로젝트>/...' 이면 'workplace/<프로젝트>' 를 돌려준다."""
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "workplace":
        return "/".join(parts[:2])
    return None


def file_path_of(event: dict) -> str | None:
    tool_input = event.get("tool_input") or {}
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def regex_hit(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern
    return None


def log_event(hook: str, status: str, **fields) -> None:
    log_dir = harness_root() / ".harness" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "hook": hook, "status": status}
        record.update(fields)
        with (log_dir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def feedback(title: str, lines: list[str], footer: str = "") -> int:
    """에이전트에게 돌려줄 피드백을 stderr로 출력하고 종료 코드 2를 돌려준다."""
    out = [f"[HARNESS] {title}"]
    out += [f"  - {line}" for line in lines]
    if footer:
        out.append(footer)
    print("\n".join(out), file=sys.stderr)
    return BLOCK
