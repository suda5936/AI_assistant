"""하네스 훅 테스트 공통 도구.

실제 하네스 설정(.claude/harness.json)을 복사한 임시 루트를 만들고,
훅 스크립트를 그 루트 기준(CLAUDE_PROJECT_DIR)으로 실행한다.
HOME도 임시 폴더로 바꿔서 관리자 모드 파일이 실제 환경에 영향받지 않게 한다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / ".claude" / "hooks"


@dataclass
class Harness:
    root: Path
    home: Path

    def run(
        self, script: str, event: dict, extra_env: dict | None = None
    ) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "HOME": str(self.home)}
        env = {k: v for k, v in env.items() if not k.startswith("HARNESS_")}
        env.update(extra_env or {})
        return subprocess.run(
            [sys.executable, str(HOOKS / script)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    def run_args(
        self, script: str, args: list[str], extra_env: dict | None = None
    ) -> subprocess.CompletedProcess:
        """이벤트 없이 명령줄 인자로 실행한다 (notify.py --test 등)."""
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "HOME": str(self.home)}
        env = {k: v for k, v in env.items() if not k.startswith("HARNESS_")}
        env.update(extra_env or {})
        return subprocess.run(
            [sys.executable, str(HOOKS / script), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def admin_on(self) -> None:
        flag = self.home / ".claude" / "harness-admin"
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()

    def git_init(self, rel: str = ".") -> None:
        cwd = self.root / rel
        cwd.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    root = tmp_path / "root"
    home = tmp_path / "home"
    (root / ".claude").mkdir(parents=True)
    home.mkdir()
    shutil.copy(REPO / ".claude" / "harness.json", root / ".claude" / "harness.json")
    shutil.copy(REPO / "ruff.toml", root / "ruff.toml")
    return Harness(root=root, home=home)


def edit_event(path: Path, role: str | None = None) -> dict:
    event: dict = {"hook_event_name": "PreToolUse", "tool_name": "Write"}
    event["tool_input"] = {"file_path": str(path)}
    if role:
        event["agent_type"] = role
    return event


def bash_event(command: str, role: str | None = None) -> dict:
    event: dict = {"hook_event_name": "PreToolUse", "tool_name": "Bash"}
    event["tool_input"] = {"command": command}
    if role:
        event["agent_type"] = role
    return event
