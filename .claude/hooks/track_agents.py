#!/usr/bin/env python3
"""진행 중인 에이전트 작업 기록 (세션이 갑자기 꺼졌을 때 대비, lessons L-25).

- PreToolUse(Agent|Task): PM이 에이전트에게 일을 맡기면 .harness/state/inflight.json 에 기록
- SubagentStop: 에이전트가 끝나면 기록에서 지운다

세션이 도중에 꺼지면 기록이 남는다. 다음 세션 시작 훅(session_start.py)이 이것을
"중단된 작업"으로 보여 주고, PM은 project-status 스킬의 재개 절차대로 다시 맡긴다.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from _lib import PASS, harness_root, read_event


def inflight_path() -> Path:
    return harness_root() / ".harness" / "state" / "inflight.json"


def load() -> list[dict]:
    try:
        data = json.loads(inflight_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save(entries: list[dict]) -> None:
    path = inflight_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def started(event: dict) -> None:
    tool_input = event.get("tool_input") or {}
    entries = load()
    entries.append(
        {
            "agent": tool_input.get("subagent_type") or "general-purpose",
            "description": (tool_input.get("description") or "")[:100],
            "started": time.strftime("%Y-%m-%d %H:%M"),
            "session_id": event.get("session_id", ""),
        }
    )
    save(entries)


def stopped(event: dict) -> None:
    agent = event.get("agent_type") or ""
    entries = load()
    for i, entry in enumerate(entries):  # 같은 역할 중 가장 먼저 시작한 것을 끝난 것으로 본다
        if entry.get("agent") == agent:
            del entries[i]
            break
    save(entries)


def main() -> int:
    event = read_event()
    if event.get("hook_event_name") == "SubagentStop":
        stopped(event)
    elif event.get("tool_name") in ("Agent", "Task"):
        started(event)
    return PASS


if __name__ == "__main__":
    sys.exit(main())
