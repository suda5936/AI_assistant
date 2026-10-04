"""훅 실행기(run.sh) 테스트.

Windows의 python3 는 Microsoft Store로 연결되는 가짜 실행 파일인 경우가 많다 (lessons L-23).
가짜 python3 가 먼저 잡혀도 실제로 동작하는 파이썬으로 훅을 실행해야 한다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import HOOKS, Harness

RUN_SH = HOOKS / "run.sh"
DANGEROUS = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}


def fake_bin(tmp: Path, real_python: bool) -> Path:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python3"
    stub.write_text("#!/bin/sh\necho 'Python was not found' >&2\nexit 9009\n")
    stub.chmod(0o755)
    if real_python:
        (bin_dir / "python").symlink_to(sys.executable)
    return bin_dir


def run(bin_dir: Path, harness: Harness) -> subprocess.CompletedProcess:
    env = {
        "PATH": str(bin_dir),
        "CLAUDE_PROJECT_DIR": str(harness.root),  # 실제 harness.json이 복사된 임시 루트
        "HOME": str(harness.home),
    }
    return subprocess.run(
        ["/bin/bash", str(RUN_SH), "guard_bash.py"],
        input=json.dumps(DANGEROUS),
        capture_output=True,
        text=True,
        env={**env, "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
        timeout=60,
    )


def test_skips_fake_python3_and_runs_hook(harness: Harness, tmp_path: Path) -> None:
    result = run(fake_bin(tmp_path, real_python=True), harness)
    assert result.returncode == 2  # 훅이 실제로 실행되어 위험 명령을 막음
    assert "HARNESS" in result.stderr


def test_reports_when_no_python_found(harness: Harness, tmp_path: Path) -> None:
    result = run(fake_bin(tmp_path, real_python=False), harness)
    assert result.returncode == 1
    assert "파이썬 3.11 이상을 찾지 못해" in result.stderr
