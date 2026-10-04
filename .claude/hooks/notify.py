#!/usr/bin/env python3
"""대표(사용자)에게 바탕화면 알림을 띄우는 모듈.

에이전트가 자동으로 처리할 수 없는 일(승인, 관리자 권한, 사람의 결정)만 알린다.
- Windows(Git Bash, WSL 포함): 토스트 알림 (PowerShell)
- macOS: 알림 센터 (osascript)
- Linux: notify-send
설정이 필요 없다. 알림 도구가 없으면 .harness/notifications.md 에만 남긴다.
휴대폰으로 받으려면 scripts/start.sh 로 시작해 Claude 앱과 세션을 연결한다.

환경변수
  HARNESS_DESKTOP_DRYRUN  파일 경로. 지정하면 알림을 띄우지 않고 이 파일에 기록 (테스트용)

직접 실행:  python3 .claude/hooks/notify.py --test
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

from _lib import harness_root, load_config, log_event

TITLE_PREFIX = "[AI_assistant]"

# Windows 토스트 알림 (PowerShell). 제목·본문은 환경변수 HN_TITLE, HN_BODY로 받는다.
_WNS = "[Windows.UI.Notifications.ToastNotificationManager]"
TOAST_PS = "\n".join(
    [
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
        " ContentType = WindowsRuntime] > $null",
        f"$t = {_WNS}::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02)",
        "$x = $t.GetElementsByTagName('text')",
        "$x.Item(0).AppendChild($t.CreateTextNode($env:HN_TITLE)) > $null",
        "$x.Item(1).AppendChild($t.CreateTextNode($env:HN_BODY)) > $null",
        "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'",
        "$n = [Windows.UI.Notifications.ToastNotification]::new($t)",
        f"{_WNS}::CreateToastNotifier($app).Show($n)",
    ]
)


def already_sent(key: str, minutes: int) -> bool:
    path = harness_root() / ".harness" / "state" / "notified.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sent = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        sent = {}
    now = time.time()
    if now - sent.get(key, 0) < minutes * 60:
        return True
    sent[key] = now
    path.write_text(json.dumps(sent))
    return False


def append_local(subject: str, body: str) -> None:
    path = harness_root() / ".harness" / "notifications.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')} {subject}\n\n{body}\n")


def desktop_command(title: str, body: str) -> tuple[list[str], dict[str, str]] | None:
    """OS별 알림 명령. 제목·본문은 인자/환경변수로 넘겨 따옴표 문제와 주입을 막는다."""
    if shutil.which("powershell.exe"):  # Windows, Git Bash, WSL
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", TOAST_PS]
        return cmd, {"HN_TITLE": title, "HN_BODY": body}
    if sys.platform == "darwin" and shutil.which("osascript"):
        script = [
            "-e", "on run argv",
            "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
            "-e", "end run",
        ]  # fmt: skip
        return ["osascript", *script, title, body], {}
    if shutil.which("notify-send"):
        return ["notify-send", "--app-name=AI_assistant", title, body], {}
    return None


def show(title: str, body: str) -> str:
    """알림을 띄우고 결과('sent', 'dryrun', 'unavailable', 'error: …')를 돌려준다."""
    dryrun = os.environ.get("HARNESS_DESKTOP_DRYRUN")
    if dryrun:
        with open(dryrun, "a", encoding="utf-8") as f:
            f.write(f"{title}\n{body}\n=====\n")
        return "dryrun"
    command = desktop_command(title, body[:200])
    if command is None:
        return "unavailable"
    cmd, extra = command
    try:
        proc = subprocess.run(
            cmd, env={**os.environ, **extra}, capture_output=True, timeout=15, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"error: {exc}"
    return "sent" if proc.returncode == 0 else f"error: exit {proc.returncode}"


def send(subject: str, body: str, kind: str = "approval") -> str:
    """대표에게 알린다. 같은 내용은 일정 시간 안에 다시 보내지 않는다."""
    notify_cfg = load_config().get("notify", {})
    if not notify_cfg.get("enabled", True):
        return "disabled"
    key = hashlib.sha256(f"{kind}|{subject}|{body}".encode()).hexdigest()[:16]
    # 권한 확인 창은 같은 문구가 반복되므로 짧게, 나머지는 길게 중복을 막는다.
    minutes = (
        notify_cfg.get("dedupe_minutes_prompt", 2)
        if kind.startswith("notification")
        else notify_cfg.get("dedupe_minutes", 120)
    )
    if already_sent(key, minutes):
        return "deduped"
    append_local(subject, body)
    result = show(f"{TITLE_PREFIX} {subject}", body)
    log_event("notify", result, kind=kind, subject=subject[:80])
    return result


def main(argv: list[str]) -> int:
    if argv[:1] == ["--test"]:
        result = send("테스트 알림", "하네스 알림이 정상적으로 설정되었습니다.", kind="test")
        print(f"결과: {result}")
        if result == "unavailable":
            print("알림 도구가 없습니다 (Windows: powershell.exe, Linux: notify-send).")
        return 0 if result in ("sent", "dryrun", "deduped") else 1
    if len(argv) >= 2:
        print(send(argv[0], argv[1], kind="manual"))
        return 0
    print('사용법: notify.py --test | notify.py "<제목>" "<본문>"')
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
