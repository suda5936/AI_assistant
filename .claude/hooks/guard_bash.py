#!/usr/bin/env python3
"""PreToolUse(Bash): 위험한 명령과 역할에 맞지 않는 명령 차단.

- blocked_commands: 모든 역할에 적용 (관리자 모드에서도 적용)
- roles.<역할>.bash_deny: 그 역할에만 적용되는 규칙 묶음
  예) reviewer, qa는 셸로 파일을 쓰거나(file_write) git 기록을 바꿀 수(git_write) 없다.
- 하네스 보호: PM을 포함한 모든 역할은 셸 명령(cp, sed -i, 리다이렉트, python -c,
  git checkout 등)으로도 하네스 영역(protected_paths)을 바꿀 수 없다. 관리자 모드(사람)만 예외.
  Write/Edit 도구는 guard_write가 막으므로, 여기서는 셸로 돌아가는 길을 막는다 (lessons L-24).
"""

from __future__ import annotations

import os
import re
import shlex
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

# 명령 구분자 (2>&1 의 &는 구분자가 아님)
SEGMENT = re.compile(r"&&|\|\||(?<![>&<])&(?![>&])|[;|\n]")
REDIRECT = re.compile(r"(?:^|[^>&\d])\d?>{1,2}\s*([^\s;&|<>()]+)")
ALL_ARGS = {"rm", "touch", "truncate", "chmod", "chown", "tee", "mkdir", "rmdir", "mv", "unlink"}
LAST_ARG = {"cp", "install", "rsync", "ln"}  # 마지막 인자가 대상
PREFIX = {"sudo", "xargs", "env", "command", "nohup", "time"}
# 인터프리터 코드 안에서 파일을 바꾸는 호출
CODE_WRITES = (
    r"write_text|write_bytes|\.write\(|open\([^)]*['\"][wax]\+?['\"]|unlink|rmtree|"
    r"shutil\.|os\.(remove|rename|replace)|writeFile|appendFile|\.touch\("
)
INTERPRETER = r"\b(python[\d.]*|py|node|perl|ruby)\b[^;&|\n]*(\s-[ce]\s|\s-\s|<<)"
# 작업 트리의 파일을 바꾸는 git 명령 (하네스 저장소 대상일 때만 문제)
GIT_TREE_OPS = (
    r"\bgit\s+(checkout|restore|apply|am|stash|reset|revert|cherry-pick|pull|merge|rebase|switch)\b"
)
HARNESS_REASON = (
    "PM과 에이전트는 셸 명령으로도 하네스(.claude/, CLAUDE.md, docs/, tests/, scripts/ 등)를 "
    "수정할 수 없습니다. 하네스 문제는 STATUS의 '사용자 결정 대기'에 적어 대표에게 넘기세요."
)

GROUP_REASON = {
    "file_write": (
        "이 역할은 셸 명령으로 파일을 만들거나 바꿀 수 없습니다. 결과는 허용된 문서에만 쓰세요."
    ),
    "git_write": "이 역할은 git 기록을 바꿀 수 없습니다. 커밋은 PM이 검수 후에 합니다.",
}


def protected(token: str, cwd: Path, cfg: dict) -> bool:
    """경로 하나가 하네스 보호 영역(workplace 밖의 protected_paths)인지."""
    root = harness_root()
    raw = token.strip("'\"")
    raw = raw.replace("${CLAUDE_PROJECT_DIR}", str(root)).replace("$CLAUDE_PROJECT_DIR", str(root))
    path = Path(os.path.expanduser(raw))
    path = path if path.is_absolute() else cwd / path
    try:
        rel = Path(os.path.normpath(path)).relative_to(root).as_posix()
    except ValueError:
        return False
    if rel == "workplace" or rel.startswith("workplace/"):
        return False
    globs = cfg.get("protected_paths", [])
    return matches(rel, globs) or any(rel == g.rstrip("/*") for g in globs)


def words_of(segment: str) -> list[str]:
    try:
        words = shlex.split(segment)
    except ValueError:
        words = segment.split()
    while words and (words[0] in PREFIX or re.match(r"^\w+=", words[0])):
        words = words[1:]
    return words


def write_targets(segment: str) -> list[str]:
    """셸 명령 한 덩어리가 바꾸는 파일 경로들."""
    targets = REDIRECT.findall(segment)
    words = words_of(segment)
    if not words:
        return targets
    cmd, flags = Path(words[0]).name, [w for w in words[1:] if w.startswith("-")]
    args = [w for w in words[1:] if not w.startswith("-")]
    if cmd in ALL_ARGS:
        targets += args
    elif cmd in LAST_ARG and args:
        targets.append(args[-1])
    elif cmd == "sed" and any(f == "--in-place" or re.match(r"^-[a-zA-Z]*i", f) for f in flags):
        targets += args[1:]  # 첫 인자는 sed 스크립트
    elif cmd == "dd":
        targets += [w[3:] for w in words if w.startswith("of=")]
    return targets


def harness_write(command: str, cwd: Path, cfg: dict) -> bool:
    """셸 명령이 하네스 영역의 파일을 바꾸려 하는지 판정한다."""
    root = harness_root()
    in_project = (cwd.relative_to(root).as_posix() + "/").startswith("workplace/")
    if re.search(GIT_TREE_OPS, command) and not in_project and "workplace/" not in command:
        return True
    if re.search(INTERPRETER, command) and re.search(CODE_WRITES, command):
        tokens = re.findall(r"[\w.~$/{}-]+", command)
        if any(("/" in t or "." in t) and protected(t, cwd, cfg) for t in tokens):
            return True
    for segment in SEGMENT.split(command):
        words = words_of(segment)
        if words[:1] == ["cd"] and len(words) > 1:  # cd 로 옮긴 위치 기준으로 판정
            cwd = Path(os.path.normpath(cwd / os.path.expanduser(words[1])))
            continue
        if any(protected(t, cwd, cfg) for t in write_targets(segment)):
            return True
    return False


def working_dir(event: dict) -> Path:
    cwd = Path(event.get("cwd") or harness_root()).resolve()
    try:
        cwd.relative_to(harness_root())
    except ValueError:
        return harness_root()
    return cwd


def decide(command: str, role: str, cfg: dict, cwd: Path | None = None) -> str | None:
    for rule in cfg.get("blocked_commands", []):
        if re.search(rule["pattern"], command):
            return rule["reason"]

    if not is_admin(cfg) and harness_write(command, cwd or harness_root(), cfg):
        return HARNESS_REASON

    roles = cfg.get("roles", {})
    groups = cfg.get("bash_rule_groups", {})
    rule = roles.get(role) or roles.get("default", {})
    for group in rule.get("bash_deny", []):
        if any(re.search(p, command) for p in groups.get(group, [])):
            return GROUP_REASON.get(group, f"'{role}' 역할에 허용되지 않은 명령입니다.")
    return None


def main() -> int:
    event = read_event()
    command = (event.get("tool_input") or {}).get("command", "")
    if not command:
        return PASS

    role = role_of(event)
    reason = decide(command, role, load_config(), working_dir(event))
    if reason is None:
        return PASS

    log_event("guard_bash", "block", role=role, command=command[:200])
    return feedback("명령 차단", [command[:200], reason])


if __name__ == "__main__":
    sys.exit(main())
