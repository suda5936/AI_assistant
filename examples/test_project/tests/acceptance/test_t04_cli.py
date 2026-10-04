"""T-04 인수 테스트: CLI 수준 (명세 AC-1 ~ AC-10)."""

import runpy
import sys

import pytest
from todo.cli import main


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "data.json"
    monkeypatch.setenv("TODO_FILE", str(path))
    return path


def run(capsys, *args):
    code = main(list(args))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# AC-1
def test_ac1_python_m_todo_entrypoint_uses_todo_file(store, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["todo", "add", "진입점"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("todo", run_name="__main__")
    assert exc.value.code == 0
    assert "추가됨: #1 진입점" in capsys.readouterr().out
    assert store.exists()


def test_ac1_default_file_is_todo_json_in_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TODO_FILE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert run(capsys, "add", "x")[0] == 0
    assert (tmp_path / "todo.json").exists()


def test_ac1_empty_env_falls_back_to_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TODO_FILE", "")
    monkeypatch.chdir(tmp_path)
    assert run(capsys, "add", "x")[0] == 0
    assert (tmp_path / "todo.json").exists()


# AC-2
def test_ac2_add_output_and_incrementing_ids(store, capsys):
    assert run(capsys, "add", "우유 사기") == (0, "추가됨: #1 우유 사기\n", "")
    assert run(capsys, "add", "운동") == (0, "추가됨: #2 운동\n", "")


def test_ac2_deleted_number_not_reused_across_runs(store, capsys):
    run(capsys, "add", "a")
    run(capsys, "add", "b")
    run(capsys, "delete", "2")
    code, out, _ = run(capsys, "add", "c")
    assert (code, out) == (0, "추가됨: #3 c\n")
    # 마지막 항목 삭제 후에도 재사용 안 함
    run(capsys, "delete", "3")
    assert run(capsys, "add", "d")[1] == "추가됨: #4 d\n"


# AC-3
@pytest.mark.parametrize("title", ["", " ", "   ", "\t", "\n "])
def test_ac3_blank_title_rejected_and_nothing_saved(store, capsys, title):
    code, out, err = run(capsys, "add", title)
    assert code == 1
    assert out == ""
    assert err.strip() == "오류: 제목을 입력하세요"
    assert not store.exists()


def test_ac3_blank_title_does_not_change_existing_file(store, capsys):
    run(capsys, "add", "a")
    before = store.read_bytes()
    assert run(capsys, "add", "  ")[0] == 1
    assert store.read_bytes() == before


# AC-4
def test_ac4_100_chars_allowed(store, capsys):
    title = "가" * 100
    assert run(capsys, "add", title) == (0, f"추가됨: #1 {title}\n", "")


def test_ac4_101_chars_rejected(store, capsys):
    code, out, err = run(capsys, "add", "a" * 101)
    assert code == 1
    assert out == ""
    assert err.strip() == "오류: 제목은 100자 이하여야 합니다"
    assert not store.exists()


# AC-5
def test_ac5_empty_list_message_no_file(store, capsys):
    assert run(capsys, "list") == (0, "할 일이 없습니다\n", "")
    assert not store.exists()


def test_ac5_empty_after_deleting_all(store, capsys):
    run(capsys, "add", "a")
    run(capsys, "delete", "1")
    assert run(capsys, "list") == (0, "할 일이 없습니다\n", "")


# AC-6
def test_ac6_list_format_and_order(store, capsys):
    run(capsys, "add", "우유 사기")
    run(capsys, "add", "운동")
    run(capsys, "add", "책")
    run(capsys, "done", "1")
    code, out, err = run(capsys, "list")
    assert code == 0
    assert err == ""
    assert out == "#1 [x] 우유 사기\n#2 [ ] 운동\n#3 [ ] 책\n"


# AC-7
def test_ac7_done_then_already_done(store, capsys):
    run(capsys, "add", "우유 사기")
    assert run(capsys, "done", "1") == (0, "완료: #1 우유 사기\n", "")
    before = store.read_bytes()
    assert run(capsys, "done", "1") == (0, "이미 완료됨: #1\n", "")
    assert store.read_bytes() == before
    assert "[x]" in run(capsys, "list")[1]


# AC-8
def test_ac8_delete_output_and_gone_from_list(store, capsys):
    run(capsys, "add", "a")
    run(capsys, "add", "b")
    assert run(capsys, "delete", "1") == (0, "삭제됨: #1 a\n", "")
    assert run(capsys, "list")[1] == "#2 [ ] b\n"


# AC-9
@pytest.mark.parametrize("cmd", ["done", "delete"])
@pytest.mark.parametrize("raw", ["99", "0", "abc", "-1", "1.5", ""])
def test_ac9_missing_or_nonnumeric_id(store, capsys, cmd, raw):
    run(capsys, "add", "a")
    before = store.read_bytes()
    code, out, err = run(capsys, cmd, raw)
    assert code == 1
    assert out == ""
    assert err.strip() == f"오류: #{raw} 할 일을 찾을 수 없습니다"
    assert store.read_bytes() == before


def test_ac9_deleted_id_then_done_fails(store, capsys):
    run(capsys, "add", "a")
    run(capsys, "delete", "1")
    assert run(capsys, "done", "1")[0] == 1
    assert run(capsys, "delete", "1")[0] == 1


# AC-10
def test_ac10_persistence_across_runs(store, capsys):
    run(capsys, "add", "a")
    run(capsys, "add", "b")
    run(capsys, "done", "2")
    run(capsys, "delete", "1")
    assert run(capsys, "list")[1] == "#2 [x] b\n"


@pytest.mark.parametrize("cmd", [["list"], ["add", "x"], ["done", "1"], ["delete", "1"]])
@pytest.mark.parametrize(
    "content",
    [b"{broken", b"", b"[]", b'{"next_id": 1}', b"\xff\xfe\x00", b'{"next_id":"1","tasks":[]}'],
)
def test_ac10_corrupt_file_exit_2_and_untouched(store, capsys, cmd, content):
    store.write_bytes(content)
    code, out, err = run(capsys, *cmd)
    assert code == 2
    assert out == ""
    assert err.strip() == f"오류: 저장 파일을 읽을 수 없습니다: {store}"
    assert store.read_bytes() == content


def test_ac10_path_is_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TODO_FILE", str(tmp_path))
    code, _, err = run(capsys, "list")
    assert code == 2
    assert "저장 파일을 읽을 수 없습니다" in err


# 설계 보충: 사용법 오류
@pytest.mark.parametrize(
    "args", [[], ["foo"], ["add"], ["add", "a", "b"], ["list", "x"], ["done"], ["delete", "1", "2"]]
)
def test_usage_errors_exit_1_no_file(store, capsys, args):
    code, out, err = run(capsys, *args)
    assert code == 1
    assert out == ""
    assert err.startswith("오류: ")
    assert not store.exists()
