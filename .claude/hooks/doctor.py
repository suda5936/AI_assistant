#!/usr/bin/env python3
"""개발 도구 점검과 자동 설치.

도구를 두 종류로 나눈다.
- 자동(auto): 관리자 권한 없이 사용자 영역에 설치할 수 있다 -> 에이전트가 바로 설치 (--fix)
- 사람(human): 시스템 설치나 관리자 권한이 필요하다 -> 설치 명령과 함께 대표에게 알림 (--notify)

사용법
  python3 .claude/hooks/doctor.py              점검 결과 출력
  python3 .claude/hooks/doctor.py --fix        자동 설치 가능한 것은 설치
  python3 .claude/hooks/doctor.py --notify     사람이 설치해야 하는 것은 알림으로 요청
  python3 .claude/hooks/doctor.py --service    웹 서비스 도구(node, npm, 브라우저)까지 점검
  python3 .claude/hooks/doctor.py --brief      없는 것만 한 줄씩 (세션 시작 훅용)
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PY = sys.executable


@dataclass
class Tool:
    name: str
    why: str
    found: bool
    tier: str  # "auto" | "human"
    install: dict[str, str]  # OS -> 설치 명령
    service_only: bool = False


def os_key() -> str:
    system = platform.system()
    if system == "Windows" or os.environ.get("MSYSTEM"):  # Git Bash도 Windows
        return "windows"
    if system == "Darwin":
        return "mac"
    return "linux"


def runs(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def python_ok() -> bool:
    return sys.version_info >= (3, 11)


def browsers_ok() -> bool:
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path.home() / ".cache" / "ms-playwright"
    )
    win = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    return any(p.is_dir() and any(p.glob("chromium*")) for p in (Path(base), win))


def tools() -> list[Tool]:
    pip_user = f"{PY} -m pip install --user"
    return [
        Tool(
            "python3.11+",
            "하네스 훅과 백엔드",
            python_ok(),
            "human",
            {
                "windows": "winget install -e --id Python.Python.3.12",
                "mac": "brew install python@3.12",
                "linux": "sudo apt-get install -y python3 python3-venv python3-pip",
            },
        ),
        Tool(
            "git",
            "프로젝트 기록",
            bool(shutil.which("git")),
            "human",
            {
                "windows": "winget install -e --id Git.Git",
                "mac": "xcode-select --install",
                "linux": "sudo apt-get install -y git",
            },
        ),
        Tool(
            "make",
            "표준 명령(make check 등)",
            bool(shutil.which("make")),
            "human",
            {
                "windows": (
                    "winget install -e --id GnuWin32.Make  "
                    "(설치 후 PATH에 C:\\Program Files (x86)\\GnuWin32\\bin 추가)"
                ),
                "mac": "xcode-select --install",
                "linux": "sudo apt-get install -y make",
            },
        ),
        Tool(
            "ruff",
            "파이썬 린트·포맷 (수정 시 검사)",
            bool(shutil.which("ruff")),
            "auto",
            {k: f"{pip_user} ruff" for k in ("windows", "mac", "linux")},
        ),
        Tool(
            "pytest",
            "테스트",
            runs([PY, "-m", "pytest", "--version"]),
            "auto",
            {k: f"{pip_user} pytest" for k in ("windows", "mac", "linux")},
        ),
        Tool(
            "node/npm",
            "프론트엔드",
            bool(shutil.which("node") and shutil.which("npm")),
            "human",
            {
                "windows": "winget install -e --id OpenJS.NodeJS.LTS",
                "mac": "brew install node@22",
                "linux": "sudo apt-get install -y nodejs npm  (Node 22 권장: nodesource 저장소)",
            },
            service_only=True,
        ),
        Tool(
            "playwright 브라우저",
            "E2E",
            browsers_ok(),
            "auto",
            {k: "npx -y playwright@1.56.1 install chromium" for k in ("windows", "mac", "linux")},
            service_only=True,
        ),
    ]


def check(service: bool) -> list[Tool]:
    return [t for t in tools() if service or not t.service_only]


def fix(missing: list[Tool], osk: str) -> list[tuple[str, bool]]:
    results = []
    for tool in missing:
        if tool.tier != "auto":
            continue
        cmd = tool.install[osk]
        # 자동 설치 명령은 위에 고정된 문자열뿐이라 셸 없이 나눠서 실행한다.
        ok = subprocess.run(shlex.split(cmd), capture_output=True, timeout=900).returncode == 0
        results.append((tool.name, ok))
    return results


def notify_human(missing: list[Tool], osk: str) -> str:
    from notify import send

    human = [t for t in missing if t.tier == "human"]
    if not human:
        return "nothing"
    lines = [
        "에이전트가 자동으로 설치할 수 없는 도구가 있습니다 (관리자 권한 또는 시스템 설치 필요).",
        "",
    ]
    for t in human:
        lines += [f"- {t.name} ({t.why})", f"    설치: {t.install[osk]}"]
    lines += [
        "",
        "설치 후 터미널(또는 VS Code)을 다시 시작하고 claude 에서 '이어서 진행해'라고 입력하세요.",
    ]
    return send(
        f"도구 설치 필요: {', '.join(t.name for t in human)}", "\n".join(lines), kind="doctor"
    )


def main(argv: list[str]) -> int:
    service = "--service" in argv
    osk = os_key()
    result = check(service)
    missing = [t for t in result if not t.found]

    if "--fix" in argv and missing:
        for name, ok in fix(missing, osk):
            print(f"자동 설치 {'성공' if ok else '실패'}: {name}")
        result = check(service)
        missing = [t for t in result if not t.found]

    if "--brief" in argv:
        for t in missing:
            print(f"- {t.name} 없음 ({'자동 설치 가능' if t.tier == 'auto' else '사람 설치 필요'})")
        return 0

    print(f"[doctor] OS: {osk}")
    for t in result:
        mark = (
            "✅" if t.found else ("🔧 자동 설치 가능" if t.tier == "auto" else "🙋 사람 설치 필요")
        )
        print(f"  {t.name:<20} {mark}" + ("" if t.found else f"  ->  {t.install[osk]}"))

    if "--notify" in argv and missing:
        print(f"알림 요청: {notify_human(missing, osk)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
