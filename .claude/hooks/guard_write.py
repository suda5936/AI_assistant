#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit|NotebookEdit): 역할별 쓰기 권한 검사.

판정 순서
1. 비밀 파일(.env, 키)은 누구도 수정할 수 없다. (.env.example 은 예외)
2. workplace 밖(하네스 영역)은 관리자 모드(사람이 ~/.claude/harness-admin 파일을
   만든 경우)에서만 수정할 수 있다.
3. workplace 안은 관리자 모드여도 역할별 권한표(harness.json의 roles)의 allow/deny 에 따른다.
하네스 저장소 밖의 경로(임시 폴더 등)는 관여하지 않는다.
"""

from __future__ import annotations

import sys

from _lib import (
    PASS,
    feedback,
    file_path_of,
    is_admin,
    load_config,
    log_event,
    matches,
    matches_name,
    read_event,
    rel_path,
    role_of,
)


def decide(rel: str, role: str, cfg: dict) -> str | None:
    """차단 사유를 돌려준다. 통과면 None."""
    if matches_name(rel, cfg.get("secret_paths", [])) and not matches_name(
        rel, cfg.get("secret_path_exceptions", [])
    ):
        return (
            "비밀 파일은 에이전트가 수정할 수 없습니다. "
            "값은 사람이 직접 넣고, 예시는 .env.example에 쓰세요."
        )
    if not rel.startswith("workplace/"):
        # workplace 밖 = 하네스 영역. 관리자 모드(사람)만 수정할 수 있다.
        if is_admin(cfg):
            return None
        if matches(rel, cfg.get("protected_paths", [])):
            return (
                "하네스 설정 파일입니다. 대표(사용자)만 수정합니다. "
                "필요하면 작업을 멈추고 이유와 함께 요청하세요."
            )
        return "workplace 밖의 파일은 수정할 수 없습니다 (절대 규칙 4)."

    # workplace 안에서는 관리자 모드여도 역할 규칙을 그대로 적용한다.
    roles = cfg.get("roles", {})
    rule = roles.get(role) or roles.get("default", {})
    if matches(rel, rule.get("deny", [])) or not matches(rel, rule.get("allow", [])):
        allowed = ", ".join(rule.get("allow", [])) or "없음"
        return f"'{role}' 역할은 이 파일을 수정할 수 없습니다. 허용 경로: {allowed}"
    return None


def main() -> int:
    event = read_event()
    file_path = file_path_of(event)
    if not file_path:
        return PASS
    rel = rel_path(file_path)
    if rel is None:
        return PASS

    cfg = load_config()
    role = role_of(event)
    reason = decide(rel, role, cfg)
    if reason is None:
        return PASS

    log_event("guard_write", "block", role=role, file=rel)
    return feedback(
        f"쓰기 차단: {rel}",
        [reason],
        "다른 역할의 일이라면 직접 하지 말고 결과 보고에 '담당 역할에게 넘길 내용'으로 적으세요.",
    )


if __name__ == "__main__":
    sys.exit(main())
