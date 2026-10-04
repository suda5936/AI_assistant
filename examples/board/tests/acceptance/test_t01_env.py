"""T-01 기반 태스크 인수 테스트 (AC 없음): 설계 문서의 실행 방법과 공개 인터페이스."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(BACKEND / "src")}
    env.pop("DATABASE_URL", None)
    env.pop("SESSION_COOKIE_SECURE", None)
    env.update(extra or {})
    return env


def _run_py(code: str, env_extra: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=_env(env_extra),
        cwd=BACKEND,
    )


def test_t01_make_targets_exist():
    out = subprocess.run(
        ["make", "-n", "setup", "check", "audit", "coverage", "openapi", "dev-backend"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr


def test_t01_env_example_lists_settings():
    text = (ROOT / ".env.example").read_text()
    for name in ["DATABASE_URL", "SESSION_COOKIE_SECURE", "API_PROXY_TARGET", "VITE_API_BASE_URL"]:
        assert name in text


def test_t01_gitignore_covers_db_and_venv():
    text = (ROOT / ".gitignore").read_text()
    assert ".env" in text and ".venv" in text and "node_modules" in text


@pytest.mark.parametrize("value", ["true", "1", "yes", "false", "0", "no", ""])
def test_t01_secure_flag_valid_values_load(value):
    r = _run_py(
        "from board.config import load_settings; load_settings()",
        {"SESSION_COOKIE_SECURE": value},
    )
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("value", ["maybe", "2", "tru"])
def test_t01_secure_flag_invalid_value_raises_valueerror(value):
    r = _run_py(
        "from board.config import load_settings; load_settings()",
        {"SESSION_COOKIE_SECURE": value},
    )
    assert r.returncode != 0 and "ValueError" in r.stderr


def test_t01_default_settings_session_ttl_7_days_and_secure_off():
    r = _run_py(
        "import datetime as d; from board.config import load_settings;"
        "s=load_settings(); assert s.session_ttl==d.timedelta(days=7);"
        "assert not s.session_cookie_secure"
    )
    assert r.returncode == 0, r.stderr


def test_t01_timeutil_naive_utc_and_iso_format():
    code = (
        "import datetime as d; from board.timeutil import utc_now,to_iso_utc;"
        "n=utc_now(); assert n.tzinfo is None;"
        "assert abs((d.datetime.now(d.timezone.utc).replace(tzinfo=None)-n).total_seconds())<5;"
        "assert to_iso_utc(d.datetime(2026,1,2,3,4,5))=='2026-01-02T03:04:05Z'"
    )
    r = _run_py(code)
    assert r.returncode == 0, r.stderr


def test_t01_app_importable_and_create_app_returns_distinct_apps():
    r = _run_py(
        "from board.main import create_app, app;"
        "a=create_app(); b=create_app(); assert a is not b; assert app is not None"
    )
    assert r.returncode == 0, r.stderr


def test_t01_openapi_export_writes_json(tmp_path):
    out = tmp_path / "openapi.json"
    r = subprocess.run(
        [sys.executable, "-m", "board.openapi_export", str(out)],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=BACKEND,
    )
    assert r.returncode == 0, r.stderr
    assert "openapi" in json.loads(out.read_text())


def test_t01_server_starts_and_responds(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    p = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "board.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=BACKEND,
        env=_env({"DATABASE_URL": f"sqlite:///{tmp_path}/t.db"}),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        status = None
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/none")
            except urllib.error.HTTPError as e:
                status = e.code
                break
            except OSError:
                time.sleep(0.2)
        assert status == 404
    finally:
        p.terminate()
        p.wait(timeout=10)
