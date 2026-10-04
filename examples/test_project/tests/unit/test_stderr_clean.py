"""실제 프로세스처럼 로깅 핸들러가 없을 때 stderr에 로그가 새지 않는지 확인하는 회귀 테스트.

pytest는 루트 로거에 캡처 핸들러를 붙여 lastResort 동작을 가린다. 그래서 루트 핸들러를
비우고 lastResort를 현재 stderr로 향하게 해 실제 프로세스 환경을 재현한다.
"""

import logging
import runpy
import sys
from pathlib import Path

import pytest
from todo import cli

CORRUPT_MESSAGE_PREFIX = "오류: 저장 파일을 읽을 수 없습니다: "
WRITE_MESSAGE_PREFIX = "오류: 저장 파일을 쓸 수 없습니다: "


def go_bare(monkeypatch: pytest.MonkeyPatch) -> None:
    """루트 로거 핸들러를 없애고 lastResort를 현재 sys.stderr로 쓰는 핸들러로 바꾼다.

    pytest는 테스트 호출 직전에 루트 핸들러를 붙이므로 반드시 테스트 본문에서 호출한다.
    """
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    monkeypatch.setattr(logging, "lastResort", logging.StreamHandler(sys.stderr))


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """TODO_FILE을 임시 경로로 지정하고 그 경로를 돌려준다."""
    path = tmp_path / "data.json"
    monkeypatch.setenv("TODO_FILE", str(path))
    return path


def run_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *args: str
) -> tuple[int, str]:
    """핸들러 없는 환경에서 main을 호출하고 (종료 코드, stderr)를 돌려준다."""
    go_bare(monkeypatch)
    code = cli.main(list(args))
    return code, capsys.readouterr().err


def test_corrupt_file_stderr_is_single_error_line(
    store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store.write_text("{깨짐", encoding="utf-8")
    code, err = run_main(monkeypatch, capsys, "list")
    assert code == 2
    assert err == f"{CORRUPT_MESSAGE_PREFIX}{store}\n"


def test_write_failure_encoding_stderr_is_single_error_line(
    store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, err = run_main(monkeypatch, capsys, "add", "\ud800")
    assert code == 2
    assert err == f"{WRITE_MESSAGE_PREFIX}{store}\n"


def test_write_failure_oserror_stderr_is_single_error_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_dir_file = tmp_path / "no_such_dir" / "data.json"
    monkeypatch.setenv("TODO_FILE", str(missing_dir_file))
    code, err = run_main(monkeypatch, capsys, "add", "a")
    assert code == 2
    assert err == f"{WRITE_MESSAGE_PREFIX}{missing_dir_file}\n"


def test_runpy_corrupt_file_stderr_is_single_error_line(
    store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store.write_text("{깨짐", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["todo", "add", "x"])
    go_bare(monkeypatch)
    with pytest.raises(SystemExit) as info:
        runpy.run_module("todo", run_name="__main__")
    assert info.value.code == 2
    assert capsys.readouterr().err == f"{CORRUPT_MESSAGE_PREFIX}{store}\n"
    assert store.read_text(encoding="utf-8") == "{깨짐"
