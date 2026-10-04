"""M1 통합 검증: `python -m todo` 진입점(runpy)으로 docs/milestones/M1.md 시나리오 1~9 실행.

회사 ruff 규칙(S603)상 subprocess를 쓸 수 없어 runpy로 `todo.__main__`을 실행한다.
실제 프로세스 실행은 QA 문서(docs/qa/M1-int-r1.md)의 수동 실행 기록을 참고한다.
"""

import runpy
import sys

import pytest


@pytest.fixture
def run(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TODO_FILE", raising=False)

    def _run(*args: str, todo_file: str | None = None):
        if todo_file is not None:
            monkeypatch.setenv("TODO_FILE", todo_file)
        else:
            monkeypatch.delenv("TODO_FILE", raising=False)
        monkeypatch.setattr(sys, "argv", ["todo", *args])
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("todo", run_name="__main__")
        out = capsys.readouterr()
        return exc.value.code, out.out, out.err

    return _run


def test_m1_int_scenarios_1_to_9(run, tmp_path):
    f = tmp_path / "todo.json"

    assert run("list") == (0, "할 일이 없습니다\n", "")
    assert not f.exists()

    assert run("add", "우유 사기") == (0, "추가됨: #1 우유 사기\n", "")
    assert run("add", "운동") == (0, "추가됨: #2 운동\n", "")

    assert run("done", "1") == (0, "완료: #1 우유 사기\n", "")
    assert run("done", "1") == (0, "이미 완료됨: #1\n", "")

    assert run("list") == (0, "#1 [x] 우유 사기\n#2 [ ] 운동\n", "")

    assert run("delete", "2") == (0, "삭제됨: #2 운동\n", "")
    assert run("add", "책 읽기") == (0, "추가됨: #3 책 읽기\n", "")

    assert run("done", "2") == (1, "", "오류: #2 할 일을 찾을 수 없습니다\n")
    assert run("delete", "abc") == (1, "", "오류: #abc 할 일을 찾을 수 없습니다\n")

    before = f.read_bytes()
    assert run("add", "") == (1, "", "오류: 제목을 입력하세요\n")
    assert run("add", "   ") == (1, "", "오류: 제목을 입력하세요\n")
    assert run("add", "a" * 101) == (1, "", "오류: 제목은 100자 이하여야 합니다\n")
    assert f.read_bytes() == before
    assert run("add", "a" * 100) == (0, f"추가됨: #4 {'a' * 100}\n", "")

    before = f.read_bytes()
    other = tmp_path / "other.json"
    assert run("add", "다른", todo_file=str(other)) == (0, "추가됨: #1 다른\n", "")
    assert other.exists()
    assert f.read_bytes() == before

    f.write_bytes("{깨짐".encode())
    broken = f.read_bytes()
    msg = "오류: 저장 파일을 읽을 수 없습니다: todo.json\n"
    assert run("list") == (2, "", msg)
    assert run("add", "x") == (2, "", msg)
    assert f.read_bytes() == broken
