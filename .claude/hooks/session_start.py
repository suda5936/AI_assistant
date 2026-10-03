#!/usr/bin/env python3
"""SessionStart: 진행 중인 프로젝트의 STATUS 요약을 세션 시작 시 PM에게 보여준다.

stdout 으로 출력한 내용이 새 세션의 컨텍스트에 들어간다.
세션이 끊기거나 컨텍스트가 비워져도 PM이 어디서부터 이어갈지 알 수 있게 한다.
"""

from __future__ import annotations

import re
import sys

from _lib import PASS, harness_root

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


def main() -> int:
    workplace = harness_root() / "workplace"
    if not workplace.is_dir():
        return PASS
    active = []
    for status in sorted(workplace.glob("*/STATUS.md")):
        text = status.read_text(encoding="utf-8")
        if not DONE.search(text):
            active.append((status.parent.name, text))
    if not active:
        return PASS

    out = [
        "[HARNESS] 진행 중인 프로젝트가 있습니다. project-status 스킬의 세션 재개 절차를 따르세요."
    ]
    for name, text in active:
        out.append(f"\n--- workplace/{name}/STATUS.md (요약) ---")
        out.append(summarize(text))
    print("\n".join(out))
    return PASS


if __name__ == "__main__":
    sys.exit(main())
