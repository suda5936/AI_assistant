#!/usr/bin/env python3
"""대표(사용자)에게 메일로 알리는 모듈.

에이전트가 자동으로 처리할 수 없는 일(승인, 관리자 권한, 사람의 결정)만 메일로 보낸다.

설정 (하네스 루트의 .env 또는 환경변수. .env는 git에 올라가지 않고 에이전트는 읽을 수 없다)
  HARNESS_SMTP_HOST      기본 smtp.naver.com
  HARNESS_SMTP_PORT      기본 465 (SSL)
  HARNESS_SMTP_USER      보내는 계정 (예: 네이버 아이디@naver.com)
  HARNESS_SMTP_PASSWORD  비밀번호 또는 애플리케이션 비밀번호
  HARNESS_NOTIFY_TO      받는 주소 (없으면 harness.json의 notify.to)
  HARNESS_NOTIFY_DRYRUN  파일 경로. 지정하면 실제로 보내지 않고 이 파일에 기록 (테스트용)

설정이 없으면 보내지 않고 .harness/notifications.md 에만 남긴다.
같은 내용은 notify.dedupe_minutes 동안 다시 보내지 않는다.

직접 실행:  python3 .claude/hooks/notify.py --test     (테스트 메일)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import smtplib
import ssl
import subprocess
import sys
import time
from email.message import EmailMessage

from _lib import harness_root, load_config, log_event

SUBJECT_PREFIX = "[AI_assistant]"


def load_env() -> dict[str, str]:
    """환경변수 + 하네스 루트 .env (환경변수가 우선)."""
    values: dict[str, str] = {}
    env_file = harness_root() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("HARNESS_")})
    return values


def recipient(env: dict[str, str], cfg: dict) -> str:
    return env.get("HARNESS_NOTIFY_TO") or cfg.get("notify", {}).get("to", "")


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


def build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = f"{SUBJECT_PREFIX} {subject}"
    footer = (
        "\n\n---\n이 메일은 AI_assistant 하네스가 자동으로 보냈습니다.\n"
        "처리 방법: AI_assistant 폴더에서 claude 를 실행하고 PM의 질문에 답하거나 승인하세요.\n"
    )
    msg.set_content(body + footer)
    return msg


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


def desktop_command(title: str, body: str) -> tuple[list[str], dict[str, str]] | None:
    """OS별 바탕화면 알림 명령. 제목·본문은 인자/환경변수로 넘겨 따옴표 문제와 주입을 막는다."""
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


def send_desktop(title: str, body: str, env: dict[str, str]) -> str:
    dryrun = env.get("HARNESS_DESKTOP_DRYRUN")
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
    """바탕화면 알림과 메일을 보낸다. 결과는 'desktop=…, email=…' 형식."""
    cfg = load_config()
    notify_cfg = cfg.get("notify", {})
    if not notify_cfg.get("enabled", True):
        return "disabled"
    env = load_env()
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
    results = []
    channels = notify_cfg.get("channels", ["desktop", "email"])
    if "desktop" in channels:
        desktop = send_desktop(f"{SUBJECT_PREFIX} {subject}", body, env)
        log_event("notify", desktop, channel="desktop", kind=kind, subject=subject[:80])
        results.append(f"desktop={desktop}")
    if "email" in channels:
        email = send_email(subject, body, kind, env, cfg)
        results.append(f"email={email}")
    return ", ".join(results)


def send_email(subject: str, body: str, kind: str, env: dict[str, str], cfg: dict) -> str:
    """메일 발송 결과('sent', 'dryrun', 'not_configured', 'error: …')."""
    to = recipient(env, cfg)
    dryrun = env.get("HARNESS_NOTIFY_DRYRUN")
    user, password = env.get("HARNESS_SMTP_USER"), env.get("HARNESS_SMTP_PASSWORD")
    if dryrun:
        msg = build_message(user or "dryrun@localhost", to, subject, body)
        with open(dryrun, "a", encoding="utf-8") as f:
            f.write(msg.as_string() + "\n=====\n")
        result = "dryrun"
    elif not (to and user and password):
        result = "not_configured"
    else:
        host = env.get("HARNESS_SMTP_HOST", "smtp.naver.com")
        port = int(env.get("HARNESS_SMTP_PORT", "465"))
        try:
            msg = build_message(user, to, subject, body)
            context = ssl.create_default_context()
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
                    smtp.login(user, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=20) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(user, password)
                    smtp.send_message(msg)
            result = "sent"
        except (OSError, smtplib.SMTPException) as exc:
            result = f"error: {exc}"
    log_event("notify", result, channel="email", kind=kind, subject=subject[:80])
    return result


def main(argv: list[str]) -> int:
    if argv[:1] == ["--test"]:
        result = send("테스트 알림", "하네스 알림이 정상적으로 설정되었습니다.", kind="test")
        print(f"결과: {result}")
        if "email=not_configured" in result:
            print("메일도 받으려면 .env 에 HARNESS_SMTP_USER, HARNESS_SMTP_PASSWORD 를 설정하세요.")
        if "desktop=unavailable" in result:
            print("바탕화면 알림 도구가 없습니다 (Windows: powershell.exe, Linux: notify-send).")
        return 0 if ("=sent" in result or "=dryrun" in result or result == "deduped") else 1
    if len(argv) >= 2:
        print(send(argv[0], argv[1], kind="manual"))
        return 0
    print('사용법: notify.py --test | notify.py "<제목>" "<본문>"')
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
