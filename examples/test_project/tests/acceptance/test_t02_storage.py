"""T-02 인수 테스트: AC-1(저장 경로 결정), AC-10(저장 유지, 손상 파일)."""

import json
import os
from pathlib import Path

import pytest
from todo import storage
from todo.errors import StorageError
from todo.models import Task, TodoList


def _sample() -> TodoList:
    return TodoList(
        next_id=4,
        tasks=[Task(1, "우유 사기", True), Task(3, "운동", False)],
    )


# ---------- AC-1 ----------
def test_ac1_env_var_used():
    assert storage.resolve_path({"TODO_FILE": "data/x/my.json"}) == Path("data/x/my.json")


def test_ac1_default_when_unset():
    assert storage.resolve_path({}) == Path("todo.json")


def test_ac1_empty_env_falls_back_to_default():
    assert storage.resolve_path({"TODO_FILE": ""}) == Path("todo.json")


def test_ac1_none_reads_os_environ(monkeypatch):
    monkeypatch.setenv("TODO_FILE", "data/from_os.json")
    assert storage.resolve_path() == Path("data/from_os.json")
    monkeypatch.delenv("TODO_FILE")
    assert storage.resolve_path() == Path("todo.json")


def test_ac1_constants():
    assert storage.ENV_VAR == "TODO_FILE"
    assert storage.DEFAULT_FILE_NAME == "todo.json"


# ---------- AC-10 정상 유지 ----------
def test_ac10_missing_file_gives_empty_and_creates_nothing(tmp_path):
    p = tmp_path / "none.json"
    assert storage.load(p) == TodoList()
    assert not p.exists()
    assert list(tmp_path.iterdir()) == []


def test_ac10_roundtrip_persists(tmp_path):
    p = tmp_path / "t.json"
    storage.save(p, _sample())
    assert storage.load(p) == _sample()


def test_ac10_save_format(tmp_path):
    p = tmp_path / "t.json"
    storage.save(p, _sample())
    raw = p.read_bytes()
    text = raw.decode("utf-8")
    assert "우유 사기" in text  # ensure_ascii=False
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert json.loads(text) == {
        "next_id": 4,
        "tasks": [
            {"id": 1, "title": "우유 사기", "done": True},
            {"id": 3, "title": "운동", "done": False},
        ],
    }


def test_ac10_next_id_preserved_after_all_deleted(tmp_path):
    p = tmp_path / "t.json"
    storage.save(p, TodoList(next_id=7, tasks=[]))
    assert storage.load(p).next_id == 7


def test_ac10_title_whitespace_and_empty_list_roundtrip(tmp_path):
    p = tmp_path / "t.json"
    todo = TodoList(next_id=2, tasks=[Task(1, "  양끝 공백  ", False)])
    storage.save(p, todo)
    assert storage.load(p) == todo


def test_ac10_repeated_save_overwrites_without_leftovers(tmp_path):
    p = tmp_path / "t.json"
    for i in range(1, 4):
        storage.save(p, TodoList(next_id=i + 1, tasks=[Task(i, f"t{i}")]))
    assert storage.load(p).next_id == 4
    assert [f.name for f in tmp_path.iterdir()] == ["t.json"]


# ---------- AC-10 손상 ----------
CORRUPT = {
    "empty": b"",
    "broken_json": "{깨짐".encode(),
    "bad_utf8": b"\xff\xfe\x80{}",
    "top_list": b"[]",
    "top_null": b"null",
    "no_next_id": b'{"tasks": []}',
    "no_tasks": b'{"next_id": 1}',
    "next_id_str": b'{"next_id": "1", "tasks": []}',
    "next_id_bool": b'{"next_id": true, "tasks": []}',
    "next_id_zero": b'{"next_id": 0, "tasks": []}',
    "next_id_float": b'{"next_id": 1.0, "tasks": []}',
    "tasks_not_list": b'{"next_id": 1, "tasks": {}}',
    "task_not_obj": b'{"next_id": 2, "tasks": [1]}',
    "id_bool": b'{"next_id": 2, "tasks": [{"id": true, "title": "a", "done": false}]}',
    "id_zero": b'{"next_id": 2, "tasks": [{"id": 0, "title": "a", "done": false}]}',
    "id_str": b'{"next_id": 2, "tasks": [{"id": "1", "title": "a", "done": false}]}',
    "title_int": b'{"next_id": 2, "tasks": [{"id": 1, "title": 5, "done": false}]}',
    "done_int": b'{"next_id": 2, "tasks": [{"id": 1, "title": "a", "done": 0}]}',
    "missing_done": b'{"next_id": 2, "tasks": [{"id": 1, "title": "a"}]}',
    "dup_id": (
        b'{"next_id": 3, "tasks": [{"id": 1, "title": "a", "done": false},'
        b' {"id": 1, "title": "b", "done": false}]}'
    ),
    "next_id_equal_max": b'{"next_id": 1, "tasks": [{"id": 1, "title": "a", "done": false}]}',
    "next_id_below_max": b'{"next_id": 1, "tasks": [{"id": 5, "title": "a", "done": false}]}',
    "deep_nesting": b"[" * 200000,
    "huge_int": b'{"next_id": ' + b"9" * 5000 + b', "tasks": []}',
}


@pytest.mark.parametrize("name", sorted(CORRUPT))
def test_ac10_corrupt_file_raises_storage_error_and_keeps_bytes(tmp_path, name):
    p = tmp_path / "todo.json"
    p.write_bytes(CORRUPT[name])
    with pytest.raises(StorageError) as ei:
        storage.load(p)
    assert str(ei.value) == f"저장 파일을 읽을 수 없습니다: {p}"
    assert p.read_bytes() == CORRUPT[name]


def test_ac10_path_is_directory_is_storage_error(tmp_path):
    with pytest.raises(StorageError, match="저장 파일을 읽을 수 없습니다"):
        storage.load(tmp_path)


def test_ac10_too_long_name_is_storage_error(tmp_path):
    with pytest.raises(StorageError, match="저장 파일을 읽을 수 없습니다"):
        storage.load(tmp_path / ("a" * 5000))


def test_ac10_exists_oserror_is_storage_error(monkeypatch, tmp_path):
    def boom(self, *a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "exists", boom)
    with pytest.raises(StorageError, match="저장 파일을 읽을 수 없습니다"):
        storage.load(tmp_path / "x.json")


def test_ac10_relative_path_message_kept_as_is(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("todo.json").write_text("{깨짐", encoding="utf-8")
    with pytest.raises(StorageError) as ei:
        storage.load(Path("todo.json"))
    assert str(ei.value) == "저장 파일을 읽을 수 없습니다: todo.json"


# ---------- AC-10 쓰기 실패 ----------
def test_ac10_surrogate_title_write_fails_keeps_file_and_no_temp(tmp_path):
    p = tmp_path / "t.json"
    storage.save(p, _sample())
    before = p.read_bytes()
    with pytest.raises(StorageError) as ei:
        storage.save(p, TodoList(next_id=2, tasks=[Task(1, "\udcff")]))
    assert str(ei.value) == f"저장 파일을 쓸 수 없습니다: {p}"
    assert p.read_bytes() == before
    assert [f.name for f in tmp_path.iterdir()] == ["t.json"]


def test_ac10_save_to_missing_dir_fails_without_creating_dir(tmp_path):
    p = tmp_path / "nodir" / "t.json"
    with pytest.raises(StorageError, match="저장 파일을 쓸 수 없습니다"):
        storage.save(p, _sample())
    assert not (tmp_path / "nodir").exists()


def test_ac10_replace_failure_keeps_file_and_cleans_temp(tmp_path, monkeypatch):
    p = tmp_path / "t.json"
    storage.save(p, _sample())
    before = p.read_bytes()

    def boom(*a, **k):
        raise OSError("fail")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StorageError, match="저장 파일을 쓸 수 없습니다"):
        storage.save(p, TodoList(next_id=2, tasks=[Task(1, "x")]))
    monkeypatch.undo()
    assert p.read_bytes() == before
    assert [f.name for f in tmp_path.iterdir()] == ["t.json"]


def test_ac10_non_oserror_during_replace_cleans_temp(tmp_path, monkeypatch):
    p = tmp_path / "t.json"

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError):
        storage.save(p, _sample())
    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == []


def test_ac10_corrupt_then_save_is_caller_choice_but_load_never_modifies(tmp_path):
    p = tmp_path / "t.json"
    p.write_bytes(b"{x")
    for _ in range(3):
        with pytest.raises(StorageError):
            storage.load(p)
    assert p.read_bytes() == b"{x"
