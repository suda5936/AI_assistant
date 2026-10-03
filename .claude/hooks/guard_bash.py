#!/usr/bin/env python3
"""PreToolUse(Bash): 위험한 명령과 역할에 맞지 않는 명령 차단.

- blocked_commands: 모든 역할에 적용 (관리자 모드에서도 적용)
- roles.<역할>.bash_deny: 그 역할에만 적용되는 규칙 묶음
  예) reviewer, qa는 셸로 파일을 쓰거나(file_write) git 기록을 바꿀 수(git_write) 없다.
"""

from __future__ import annotations

import re
import sys

from _lib import PASS, feedback, load_config, log_event, read_event, role_of

GROUP_REASON = {
    "file_write": (
        "이 역할은 셸 명령으로 파일을 만들거나 바꿀 수 없습니다. 결과는 허용된 문서에만 쓰세요."
    ),
    "git_write": "이 역할은 git 기록을 바꿀 수 없습니다. 커밋은 PM이 검수 후에 합니다.",
}


def decide(command: str, role: str, cfg: dict) -> str | None:
    for rule in cfg.get("blocked_commands", []):
        if re.search(rule["pattern"], command):
            return rule["reason"]

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
    reason = decide(command, role, load_config())
    if reason is None:
        return PASS

    log_event("guard_bash", "block", role=role, command=command[:200])
    return feedback("명령 차단", [command[:200], reason])


if __name__ == "__main__":
    sys.exit(main())
