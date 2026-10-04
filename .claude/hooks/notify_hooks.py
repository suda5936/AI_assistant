#!/usr/bin/env python3
"""사람의 개입이 필요한 순간을 감지해 메일로 알리는 훅.

- Notification 이벤트: Claude Code가 권한 확인을 기다리거나 입력을 기다릴 때
- Stop 이벤트 (메인 세션만): 진행 중인 프로젝트 STATUS.md 의 "사용자 결정 대기"에 항목이 있을 때
  (명세 승인, ADR, 3회 반려, 관리자 권한이 필요한 설치 등 PM이 기록한 모든 대기 사항)

메일 내용은 무엇을, 어디서, 어떻게 처리하면 되는지 한눈에 보이게 쓴다.
"""

from __future__ import annotations

import re
import sys

from _lib import PASS, harness_root, read_event, role_of
from notify import send

NONE_PATTERN = re.compile(r"^-?\s*(\(?없음\)?|없음\b)")


def section(text: str, title: str) -> list[str]:
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == f"## {title}"
            continue
        if inside and line.strip():
            lines.append(line.rstrip())
    return lines


def pending_decisions() -> list[tuple[str, list[str], list[str]]]:
    """(프로젝트, 결정 대기 항목, 현재 단계 줄) 목록."""
    result = []
    for status in sorted((harness_root() / "workplace").glob("*/STATUS.md")):
        text = status.read_text(encoding="utf-8")
        items = [i for i in section(text, "사용자 결정 대기") if not NONE_PATTERN.match(i.strip())]
        if items:
            stage = [line for line in text.splitlines() if "현재 단계" in line][:1]
            result.append((status.parent.name, items, stage))
    return result


def on_stop(event: dict) -> None:
    if role_of(event) != "main":
        return
    for project, items, stage in pending_decisions():
        body = "\n".join(
            [
                f"프로젝트: workplace/{project}",
                *(s.strip("- ") for s in stage),
                "",
                "대표님의 결정이 필요한 항목:",
                *items,
                "",
                f"자세한 내용: workplace/{project}/STATUS.md",
            ]
        )
        send(f"결정 필요: {project} ({len(items)}건)", body, kind="decision")


def on_notification(event: dict) -> None:
    message = event.get("message", "")
    kind = event.get("notification_type", "notification")
    if kind == "auth_success":
        return
    lines = [
        "Claude Code가 대표님의 응답을 기다리고 있습니다.",
        "",
        f"내용: {message}",
        f"종류: {kind}",
    ]
    pending = pending_decisions()
    if pending:
        lines += ["", "함께 대기 중인 결정:"]
        for project, items, _ in pending:
            lines += [f"[{project}]", *items]
    send(f"응답 대기: {message[:40]}", "\n".join(lines), kind=f"notification:{kind}")


def main() -> int:
    event = read_event()
    hook = event.get("hook_event_name", "")
    if hook == "Notification":
        on_notification(event)
    elif hook == "Stop":
        on_stop(event)
    return PASS  # 알림 실패가 작업을 막으면 안 된다


if __name__ == "__main__":
    sys.exit(main())
