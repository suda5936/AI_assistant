"""메일 알림(notify, notify_hooks)과 도구 점검(doctor) 테스트.

실제 메일은 보내지 않는다. HARNESS_NOTIFY_DRYRUN 으로 메일 내용을 파일에 기록해 확인한다.
"""

from __future__ import annotations

import json
from email import message_from_string, policy
from pathlib import Path

from conftest import Harness

P = "workplace/shop"
STATUS = """# STATUS: shop

- 현재 단계: 명세

## 사용자 결정 대기
- [승인] 명세 Q1~Q3 답변 필요 — docs/01_spec.md
- [설치] make 없음 — 관리자 권한 필요: winget install -e --id ezwinports.make

## 다음 할 일
- 답변 대기
"""


def dryrun_env(tmp: Path) -> dict:
    return {"HARNESS_NOTIFY_DRYRUN": str(tmp / "mail.txt")}


def mails(tmp: Path) -> str:
    """드라이런 파일의 메일들을 디코딩해 '받는사람/제목/본문' 텍스트로 돌려준다."""
    path = tmp / "mail.txt"
    if not path.exists():
        return ""
    out = []
    for raw in path.read_text(encoding="utf-8").split("\n=====\n"):
        if raw.strip():
            msg = message_from_string(raw, policy=policy.default)
            out.append(f"To: {msg['To']}\nSubject: {msg['Subject']}\n{msg.get_content()}")
    return "\n=====\n".join(out) + ("\n=====\n" if out else "")


def test_pending_decisions_are_mailed_on_stop(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    result = harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert result.returncode == 0
    mail = mails(tmp_path)
    assert "To: gustlr3308@naver.com" in mail
    assert "결정 필요: shop (2건)" in mail
    assert "winget install -e --id ezwinports.make" in mail


def test_same_mail_is_not_repeated(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    for _ in range(3):
        harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert mails(tmp_path).count("=====") == 1


def test_no_mail_when_nothing_is_pending(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", "# STATUS: shop\n\n## 사용자 결정 대기\n- 없음\n")
    harness.run("notify_hooks.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert mails(tmp_path) == ""


def test_subagent_stop_does_not_mail(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    event = {"hook_event_name": "Stop", "agent_type": "developer"}
    harness.run("notify_hooks.py", event, dryrun_env(tmp_path))
    assert mails(tmp_path) == ""


def test_permission_prompt_is_mailed(harness: Harness, tmp_path: Path) -> None:
    event = {
        "hook_event_name": "Notification",
        "notification_type": "permission_prompt",
        "message": "Claude needs your permission to use Bash",
    }
    harness.run("notify_hooks.py", event, dryrun_env(tmp_path))
    assert "Claude needs your permission to use Bash" in mails(tmp_path)


def test_without_smtp_settings_it_is_only_recorded(harness: Harness, tmp_path: Path) -> None:
    harness.write(f"{P}/STATUS.md", STATUS)
    result = harness.run("notify_hooks.py", {"hook_event_name": "Stop"})
    assert result.returncode == 0  # 설정이 없어도 작업을 막지 않는다
    local = (harness.root / ".harness" / "notifications.md").read_text(encoding="utf-8")
    assert "결정 필요: shop" in local
    log = (harness.root / ".harness" / "logs" / "events.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["status"] == "not_configured"


def test_quality_gate_give_up_is_mailed(harness: Harness, tmp_path: Path) -> None:
    harness.git_init(P)
    harness.write(f"{P}/pyproject.toml", '[project]\nname = "x"\nversion = "0"\n')
    harness.write(f"{P}/tests/unit/test_x.py", "def test_fail() -> None:\n    assert 1 == 2\n")
    for _ in range(4):
        harness.run("quality_gate.py", {"hook_event_name": "Stop"}, dryrun_env(tmp_path))
    assert "품질 게이트 중단" in mails(tmp_path)
    assert "3회 연속 실패" in mails(tmp_path)


def test_doctor_brief_lists_only_missing(harness: Harness) -> None:
    result = harness.run("doctor.py", {}, {"PATH": "/nonexistent"})
    # PATH가 비어 있으면 git, make, ruff 등이 없다고 나와야 한다
    assert result.returncode == 1
    assert "사람 설치 필요" in result.stdout
    assert "자동 설치 가능" in result.stdout
