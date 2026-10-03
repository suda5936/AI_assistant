#!/usr/bin/env python3
"""PreToolUse(Read|Grep|Glob): 역할별 읽기 제한.

qa는 "코드가 하는 일"이 아니라 "코드가 해야 하는 일"(명세)을 기준으로 검증해야 한다.
구현 코드를 읽으면 구현에 맞춘 테스트를 쓰게 되어 독립 검증이 무너진다.
그래서 roles.<역할>.read_deny 에 있는 경로는 읽을 수 없게 한다. (lessons L-14)
"""

from __future__ import annotations

import sys

from _lib import PASS, feedback, load_config, log_event, matches, read_event, rel_path, role_of


def target_of(event: dict) -> str | None:
    tool_input = event.get("tool_input") or {}
    return tool_input.get("file_path") or tool_input.get("path")


def main() -> int:
    event = read_event()
    target = target_of(event)
    if not target:
        return PASS
    rel = rel_path(target)
    if rel is None:
        return PASS

    role = role_of(event)
    rule = load_config().get("roles", {}).get(role, {})
    deny = rule.get("read_deny", [])
    # 폴더를 검색하는 경우(Grep/Glob)는 그 폴더 자체가 금지 경로 안이면 막는다.
    if not deny or not (matches(rel, deny) or matches(rel.rstrip("/") + "/", deny)):
        return PASS

    log_event("guard_read", "block", role=role, file=rel)
    return feedback(
        f"읽기 차단: {rel}",
        [
            f"'{role}' 역할은 구현 코드를 읽지 않습니다. "
            "명세(01_spec.md)와 설계 문서의 공개 인터페이스만 보세요."
        ],
        "인터페이스가 문서에 없으면 테스트를 추측해 쓰지 말고 "
        "PM에게 '설계 문서에 없음'으로 보고하세요.",
    )


if __name__ == "__main__":
    sys.exit(main())
