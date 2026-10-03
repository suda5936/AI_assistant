"""수정 시 자동 검사(check_edit) 테스트."""

from __future__ import annotations

import json

import pytest
from conftest import Harness, edit_event

P = "workplace/demo"
TODO = "TO" + "DO"  # 이 파일 자체가 TODO 규칙에 걸리지 않게 조립
NOQA = "no" + "qa"


def post(harness: Harness, rel: str, text: str, role: str = "developer"):
    path = harness.write(rel, text)
    event = edit_event(path, role)
    event["hook_event_name"] = "PostToolUse"
    return harness.run("check_edit.py", event)


def test_clean_python_passes(harness: Harness) -> None:
    code = '"""모듈."""\n\n\ndef add(a: int, b: int) -> int:\n    """더한다."""\n    return a + b\n'
    result = post(harness, f"{P}/src/app/calc.py", code)
    assert result.returncode == 0, result.stderr


def test_formatting_is_fixed_automatically(harness: Harness) -> None:
    result = post(harness, f"{P}/src/app/fmt.py", "x=[1,2 ,3]\n")
    assert result.returncode == 0, result.stderr
    assert (harness.root / f"{P}/src/app/fmt.py").read_text() == "x = [1, 2, 3]\n"


@pytest.mark.parametrize(
    ("rel", "code", "expected"),
    [
        (f"{P}/src/app/a.py", "import os\n", "F401"),
        (f"{P}/src/app/b.py", "def f() -> None:\n    print('x')\n", "T201"),
        (f"{P}/src/app/c.py", "def f() -> None:\n    breakpoint()\n", "T100"),
        (
            f"{P}/src/app/d.py",
            "def f() -> None:\n    try:\n        pass\n    except Exception:\n        pass\n",
            "BLE001",
        ),
        (f"{P}/src/app/e.py", "def f(s: str) -> object:\n    return eval(s)\n", "S307"),
        (f"{P}/src/app/g.py", f"# {TODO} 나중에\nX = 1\n", "태스크 ID"),
        (f"{P}/src/app/h.py", f"import os  # {NOQA}\n", "금지된 꼼수"),
    ],
)
def test_violations_are_fed_back(harness: Harness, rel: str, code: str, expected: str) -> None:
    result = post(harness, rel, code)
    assert result.returncode == 2
    assert expected in result.stderr


def test_print_allowed_in_cli_module(harness: Harness) -> None:
    code = '"""CLI 출력."""\n\n\ndef show(msg: str) -> None:\n    """출력한다."""\n    print(msg)\n'
    result = post(harness, f"{P}/src/app/cli.py", code)
    assert result.returncode == 0, result.stderr


def test_todo_with_task_id_is_allowed(harness: Harness) -> None:
    result = post(harness, f"{P}/src/app/t.py", f"# {TODO}(T-03): 정리\nX = 1\n")
    assert result.returncode == 0, result.stderr


def test_hardcoded_secret_is_detected(harness: Harness) -> None:
    fake = "AKIA" + "ABCDEFGHIJKLMNOP"
    result = post(harness, f"{P}/src/app/config.py", f'KEY = "{fake}"\n')
    assert result.returncode == 2
    assert "비밀값" in result.stderr


def test_long_file_is_rejected(harness: Harness) -> None:
    code = "\n".join(f"X{i} = {i}" for i in range(320)) + "\n"
    result = post(harness, f"{P}/src/app/big.py", code)
    assert result.returncode == 2
    assert "최대 300" in result.stderr


def test_invalid_json_is_detected(harness: Harness) -> None:
    result = post(harness, f"{P}/data.json", "{bad")
    assert result.returncode == 2
    assert "JSON" in result.stderr


def test_typescript_console_log_is_detected(harness: Harness) -> None:
    result = post(harness, f"{P}/frontend/src/App.tsx", "console.log('x');\n")
    assert result.returncode == 2
    assert "console.log" in result.stderr


def test_result_is_logged_with_role(harness: Harness) -> None:
    post(harness, f"{P}/src/app/a.py", "import os\n", role="developer")
    log = (harness.root / ".harness" / "logs" / "events.jsonl").read_text().splitlines()
    record = json.loads(log[-1])
    assert record["hook"] == "check_edit"
    assert record["status"] == "fail"
    assert record["role"] == "developer"
