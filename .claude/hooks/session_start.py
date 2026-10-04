#!/usr/bin/env python3
"""SessionStart: 진행 중인 프로젝트의 STATUS 요약을 세션 시작 시 PM에게 보여준다.

stdout 으로 출력한 내용이 새 세션의 컨텍스트에 들어간다.
세션이 끊기거나 컨텍스트가 비워져도 PM이 어디서부터 이어갈지 알 수 있게 한다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from _lib import PASS, harness_root, log_event, read_event
from track_agents import load, save

DONE = re.compile(r"현재 단계:\s*(완료|보류)")


SHOWN_SECTIONS = ("## 마일스톤", "## 사용자 결정 대기", "## 열린 이슈", "## 다음 할 일")


def summarize(text: str) -> str:
    """머리말(현재 단계 등)과 핵심 섹션만 골라 보여준다. 태스크 표는 생략한다."""
    keep: list[str] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line.strip()
        if not section or section in SHOWN_SECTIONS:
            keep.append(line)
    return "\n".join(line for line in keep if line.strip())[:4000]


def missing_tools() -> list[str]:
    """doctor 의 간단 점검. 빠진 도구만 한 줄씩."""
    try:
        from doctor import check
    except ImportError:
        return []
    return [
        f"- {t.name} 없음 ({'자동 설치 가능' if t.tier == 'auto' else '사람 설치 필요'})"
        for t in check(service=False)
        if not t.found
    ]


def interrupted(source: str) -> list[str]:
    """이전 세션에서 끝나지 않은 에이전트 작업. 프로세스가 새로 떴으면 모두 중단된 것이다."""
    if source not in ("startup", "resume", ""):
        return []  # compact·clear 는 같은 프로세스라 백그라운드 에이전트가 아직 돌 수 있다
    entries = load()
    if not entries:
        return []
    save([])
    log_event("session_start", "interrupted", agents=entries)
    lines = [
        "[HARNESS] 이전 세션이 아래 에이전트 작업 도중 꺼졌습니다. "
        "project-status 스킬의 '중단 복구' 절차대로 같은 작업을 다시 맡기세요."
    ]
    lines += [f"- {e['agent']}: {e['description']} (시작 {e['started']})" for e in entries]
    return lines


def git_state(project: Path) -> str:
    """커밋되지 않은 변경(= 아직 검수를 통과하지 않은 작업) 요약."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    changed = [line[3:] for line in result.stdout.splitlines() if line.strip()]
    if not changed:
        return "커밋되지 않은 변경: 없음"
    shown = ", ".join(changed[:10]) + (f" 외 {len(changed) - 10}개" if len(changed) > 10 else "")
    return f"커밋되지 않은 변경 {len(changed)}개 (검수 전 작업일 수 있음): {shown}"


def main() -> int:
    event = read_event()
    out: list[str] = interrupted(event.get("source", ""))
    tools = missing_tools()
    if tools:
        out.append("[HARNESS] 개발 도구가 빠져 있습니다. doctor 스킬대로 처리하세요.")
        out += tools

    workplace = harness_root() / "workplace"
    active = []
    for status in sorted(workplace.glob("*/STATUS.md")) if workplace.is_dir() else []:
        text = status.read_text(encoding="utf-8")
        if not DONE.search(text):
            active.append((status.parent.name, text))
    if active:
        out.append(
            "[HARNESS] 진행 중인 프로젝트가 있습니다. "
            "project-status 스킬의 세션 재개 절차를 따르세요."
        )
        for name, text in active:
            out.append(f"\n--- workplace/{name}/STATUS.md (요약) ---")
            out.append(summarize(text))
            state = git_state(workplace / name)
            if state:
                out.append(state)
    if out:
        print("\n".join(out))
    return PASS


if __name__ == "__main__":
    sys.exit(main())
