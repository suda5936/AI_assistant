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
import smtplib
import ssl
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


def send(subject: str, body: str, kind: str = "approval") -> str:
    """메일을 보내고 결과('sent', 'dryrun', 'deduped', 'not_configured', 'error: …')를 돌려준다."""
    cfg = load_config()
    notify_cfg = cfg.get("notify", {})
    if not notify_cfg.get("enabled", True):
        return "disabled"
    env = load_env()
    to = recipient(env, cfg)
    key = hashlib.sha256(f"{kind}|{subject}|{body}".encode()).hexdigest()[:16]
    if already_sent(key, notify_cfg.get("dedupe_minutes", 120)):
        return "deduped"

    append_local(subject, body)
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
    log_event("notify", result, kind=kind, subject=subject[:80])
    return result


def main(argv: list[str]) -> int:
    if argv[:1] == ["--test"]:
        result = send("테스트 메일", "하네스 메일 알림이 정상적으로 설정되었습니다.", kind="test")
        print(f"결과: {result}")
        if result == "not_configured":
            print("하네스 루트 .env 에 HARNESS_SMTP_USER, HARNESS_SMTP_PASSWORD 를 설정하세요.")
        return 0 if result in ("sent", "dryrun", "deduped") else 1
    if len(argv) >= 2:
        print(send(argv[0], argv[1], kind="manual"))
        return 0
    print('사용법: notify.py --test | notify.py "<제목>" "<본문>"')
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
