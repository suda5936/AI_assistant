"""대표 알림(notify, notify_hooks)과 도구 점검(doctor) 테스트.

실제 알림은 띄우지 않는다. HARNESS_DESKTOP_DRYRUN 으로 알림 내용을 파일에 기록해 확인한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import Harness

P = "workplace/shop"
STATUS = """# STATUS: shop

- 현재 단계: 명세

## 사용자 결정 대기
- [승인] 명세 Q1~Q3 답변 필요 — docs/01_spec.md
- [설치] make 없음 — 관리자 권한 필요: winget install -e --id GnuWin32.Make

## 다음 할 일
- 답변 대기
"""
PROMPT = {
    "hook_event_name": "Notification",
    "notification_type": "permission_prompt",
    "message": "Claude needs your permission to use Bash",
}


def dryrun_env(tmp: Path) -> dict:
    return {"HARNESS_DESKTOP_DRYRUN": str(tmp / "desktop.txt")}


def alerts(tmp: Path) -> str:
    path = tmp / "desktop.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_pending_decisions_alert_on_stop(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    result = harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert result.returncode == 0
    alert = alerts(tmp_path)
    assert "[AI_assistant] 결정 필요: shop (2건)" in alert
    assert "winget install -e --id GnuWin32.Make" in alert


def test_same_decision_is_not_repeated(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    for _ in range(3):
        harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert alerts(tmp_path).count("=====") == 1


def test_no_alert_when_nothing_is_pending(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", "# STATUS: shop\n\n## 사용자 결정 대기\n- 없음\n")
    harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert alerts(tmp_path) == ""


def test_subagent_stop_does_not_alert(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    event = {"hook_event_name": "Stop", "agent_type": "developer"}
    harness.run("notify_hooks.py", event, dryrun_env(tmp_path))
    assert alerts(tmp_path) == ""


def test_permission_prompt_alerts(harness: Harness, tmp_path: Path) -> None:
    harness.run("notify_hooks.py", PROMPT, dryrun_env(tmp_path))
    assert "Claude needs your permission to use Bash" in alerts(tmp_path)


def test_repeated_permission_prompts_still_alert(harness: Harness, tmp_path: Path) -> None:
    """권한 확인 창은 같은 문구가 반복되므로 2시간이 아니라 짧게(2분) 중복을 막는다."""
    harness.run("notify_hooks.py", PROMPT, dryrun_env(tmp_path))
    state = harness.root / ".harness" / "state" / "notified.json"
    sent = json.loads(state.read_text())
    state.write_text(json.dumps({k: v - 180 for k, v in sent.items()}))  # 3분 전으로
    harness.run("notify_hooks.py", PROMPT, dryrun_env(tmp_path))
    assert alerts(tmp_path).count("=====") == 2


def test_alerts_are_recorded_locally(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    local = (harness.root / ".harness" / "notifications.md").read_text(encoding="utf-8")
    assert "결정 필요: shop" in local


def test_quality_gate_give_up_alerts(harness: Harness, tmp_path: Path) -> None:
    harness.git_init(P)
    harness.write(f"{P}/pyproject.toml", '[project]\nname = "x"\nversion = "0"\n')
    harness.write(f"{P}/tests/unit/test_x.py", "def test_fail() -> None:\n    assert 1 == 2\n")
    for _ in range(4):
        harness.run("quality_gate.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert "품질 게이트 중단" in alerts(tmp_path)
    assert "3회 연속 실패" in alerts(tmp_path)


def test_notify_test_command(harness: Harness, tmp_path: Path) -> None:
    usage = harness.run("notify.py", {}, dryrun_env(tmp_path))
    assert usage.returncode == 1  # 인자 없으면 사용법
    result = harness.run_args("notify.py", ["--test"], dryrun_env(tmp_path))
    assert result.returncode == 0
    assert "결과: dryrun" in result.stdout


def test_doctor_lists_missing_tools(harness: Harness) -> None:
    result = harness.run("doctor.py", {}, {"PATH": "/nonexistent"})
    # PATH가 비어 있으면 git, make, ruff 등이 없다고 나와야 한다
    assert result.returncode == 1
    assert "사람 설치 필요" in result.stdout
    assert "자동 설치 가능" in result.stdout
