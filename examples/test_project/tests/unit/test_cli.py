"""cli 모듈과 __main__ 단위 테스트."""

import json
import runpy
import sys
from pathlib import Path

import pytest
from todo import cli
from todo.models import Task

USAGE = '오류: 사용법: python -m todo add "<제목>" | list | done <번호> | delete <번호>\n'


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """TODO_FILE을 임시 경로로 지정하고 그 경로를 돌려준다."""
    path = tmp_path / "data.json"
    monkeypatch.setenv("TODO_FILE", str(path))
    return path


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    """main을 호출하고 (코드, stdout, stderr)를 돌려준다."""
    code = cli.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write_raw(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestFormatTaskLine:
    def test_open(self) -> None:
        assert cli.format_task_line(Task(1, "우유")) == "#1 [ ] 우유"

    def test_done(self) -> None:
        assert cli.format_task_line(Task(12, "운동", True)) == "#12 [x] 운동"


class TestUsage:
    @pytest.mark.parametrize(
        "args",
        [(), ("foo",), ("add",), ("add", "a", "b"), ("list", "x"), ("done",), ("delete", "1", "2")],
    )
    def test_usage_error(
        self, store: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
    ) -> None:
        assert run(capsys, *args) == (1, "", USAGE)
        assert not store.exists()

    def test_usage_error_does_not_read_corrupt_file(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_raw(store, "{깨짐")
        assert run(capsys, "bogus")[0] == 1

    def test_none_argv_uses_sys_argv(
        self, store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["todo", "list"])
        assert cli.main() == 0
        assert capsys.readouterr().out == "할 일이 없습니다\n"


class TestAdd:
    def test_add_saves_and_prints(self, store: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(capsys, "add", "우유 사기") == (0, "추가됨: #1 우유 사기\n", "")
        assert run(capsys, "add", "운동") == (0, "추가됨: #2 운동\n", "")
        data = json.loads(store.read_text(encoding="utf-8"))
        assert data == {
            "next_id": 3,
            "tasks": [
                {"id": 1, "title": "우유 사기", "done": False},
                {"id": 2, "title": "운동", "done": False},
            ],
        }

    def test_add_100_chars_ok(self, store: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(capsys, "add", "가" * 100)[0] == 0

    @pytest.mark.parametrize(
        ("title", "message"),
        [
            ("", "제목을 입력하세요"),
            ("   ", "제목을 입력하세요"),
            ("가" * 101, "제목은 100자 이하여야 합니다"),
        ],
    )
    def test_invalid_title(
        self, store: Path, capsys: pytest.CaptureFixture[str], title: str, message: str
    ) -> None:
        assert run(capsys, "add", title) == (1, "", f"오류: {message}\n")
        assert not store.exists()

    def test_invalid_title_keeps_existing_file(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(capsys, "add", "a")
        before = store.read_bytes()
        assert run(capsys, "add", "")[0] == 1
        assert store.read_bytes() == before

    def test_invalid_title_wins_over_corrupt_file(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_raw(store, "{깨짐")
        assert run(capsys, "add", "")[0] == 1

    def test_surrogate_title_is_write_error(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, err = run(capsys, "add", "\udcff")
        assert (code, out) == (2, "")
        assert err == f"오류: 저장 파일을 쓸 수 없습니다: {store}\n"
        assert not store.exists()
        assert list(store.parent.iterdir()) == []


class TestList:
    def test_empty_without_file(self, store: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(capsys, "list") == (0, "할 일이 없습니다\n", "")
        assert not store.exists()

    def test_lines(self, store: Path, capsys: pytest.CaptureFixture[str]) -> None:
        run(capsys, "add", "우유 사기")
        run(capsys, "add", "운동")
        run(capsys, "done", "1")
        assert run(capsys, "list") == (0, "#1 [x] 우유 사기\n#2 [ ] 운동\n", "")

    def test_empty_after_deleting_all(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(capsys, "add", "a")
        run(capsys, "delete", "1")
        assert run(capsys, "list") == (0, "할 일이 없습니다\n", "")


class TestDone:
    def test_done_then_already_done(self, store: Path, capsys: pytest.CaptureFixture[str]) -> None:
        run(capsys, "add", "우유 사기")
        assert run(capsys, "done", "1") == (0, "완료: #1 우유 사기\n", "")
        before = store.read_bytes()
        assert run(capsys, "done", "1") == (0, "이미 완료됨: #1\n", "")
        assert store.read_bytes() == before

    def test_leading_zero_prints_stored_id(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(capsys, "add", "a")
        assert run(capsys, "done", "01") == (0, "완료: #1 a\n", "")

    @pytest.mark.parametrize("raw_id", ["2", "abc", "-1", "0", "1.5"])
    def test_not_found(self, store: Path, capsys: pytest.CaptureFixture[str], raw_id: str) -> None:
        run(capsys, "add", "a")
        before = store.read_bytes()
        assert run(capsys, "done", raw_id) == (1, "", f"오류: #{raw_id} 할 일을 찾을 수 없습니다\n")
        assert store.read_bytes() == before


class TestDelete:
    def test_delete_then_gone_and_id_not_reused(
        self, store: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(capsys, "add", "우유 사기")
        run(capsys, "add", "운동")
        assert run(capsys, "delete", "2") == (0, "삭제됨: #2 운동\n", "")
        assert run(capsys, "list")[1] == "#1 [ ] 우유 사기\n"
        assert run(capsys, "add", "책 읽기")[1] == "추가됨: #3 책 읽기\n"

    @pytest.mark.parametrize("raw_id", ["9", "abc"])
    def test_not_found(self, store: Path, capsys: pytest.CaptureFixture[str], raw_id: str) -> None:
        assert run(capsys, "delete", raw_id) == (
            1,
            "",
            f"오류: #{raw_id} 할 일을 찾을 수 없습니다\n",
        )
        assert not store.exists()


class TestCorruptFile:
    @pytest.mark.parametrize("args", [("list",), ("add", "x"), ("done", "1"), ("delete", "abc")])
    def test_read_error(
        self, store: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
    ) -> None:
        write_raw(store, "{깨짐")
        before = store.read_bytes()
        code, out, err = run(capsys, *args)
        assert (code, out) == (2, "")
        assert err == f"오류: 저장 파일을 읽을 수 없습니다: {store}\n"
        assert store.read_bytes() == before


class TestPath:
    def test_default_file_in_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("TODO_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        run(capsys, "add", "a")
        assert (tmp_path / "todo.json").exists()

    def test_default_path_in_error_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("TODO_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        write_raw(tmp_path / "todo.json", "{깨짐")
        assert run(capsys, "list")[2] == "오류: 저장 파일을 읽을 수 없습니다: todo.json\n"

    def test_env_path_leaves_default_untouched(
        self,
        tmp_path: Path,
        store: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        run(capsys, "add", "a")
        assert store.exists()
        assert not (tmp_path / "todo.json").exists()


class TestEntryPoint:
    def test_runpy_exit_code_and_storage(
        self, store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["todo", "add", "a"])
        with pytest.raises(SystemExit) as info:
            runpy.run_module("todo", run_name="__main__")
        assert info.value.code == 0
        assert capsys.readouterr().out == "추가됨: #1 a\n"
        assert store.exists()

    def test_runpy_error_code(
        self, store: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["todo"])
        with pytest.raises(SystemExit) as info:
            runpy.run_module("todo", run_name="__main__")
        assert info.value.code == 1
        assert capsys.readouterr().err == USAGE
