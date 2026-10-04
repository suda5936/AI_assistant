"""storage 단위 테스트."""

import json
import os
from pathlib import Path

import pytest
from todo import storage
from todo.errors import StorageError
from todo.models import Task, TodoList


def _write(path: Path, content: str | bytes) -> bytes:
    data = content.encode("utf-8") if isinstance(content, str) else content
    path.write_bytes(data)
    return data


def _valid(**overrides: object) -> dict:
    data: dict = {"next_id": 3, "tasks": [{"id": 1, "title": "a", "done": True}]}
    data.update(overrides)
    return data


class TestResolvePath:
    def test_env_set(self) -> None:
        assert storage.resolve_path({"TODO_FILE": "data/x.json"}) == Path("data/x.json")

    def test_env_missing(self) -> None:
        assert storage.resolve_path({}) == Path("todo.json")

    def test_env_empty(self) -> None:
        assert storage.resolve_path({"TODO_FILE": ""}) == Path("todo.json")

    def test_none_uses_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TODO_FILE", "custom.json")
        assert storage.resolve_path() == Path("custom.json")
        monkeypatch.delenv("TODO_FILE")
        assert storage.resolve_path() == Path("todo.json")


class TestLoad:
    def test_missing_file_gives_empty_and_creates_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        assert storage.load(path) == TodoList()
        assert not path.exists()

    def test_valid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        _write(path, json.dumps(_valid()))
        assert storage.load(path) == TodoList(3, [Task(1, "a", True)])

    def test_empty_tasks(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        _write(path, json.dumps({"next_id": 1, "tasks": []}))
        assert storage.load(path) == TodoList()

    def test_next_id_larger_than_max_id_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        _write(path, json.dumps(_valid(next_id=10)))
        assert storage.load(path).next_id == 10

    @pytest.mark.parametrize(
        "content",
        [
            b"",
            "{깨짐",
            b"\xff\xfe\x00bad",
            "[]",
            "null",
            '"text"',
            json.dumps({"tasks": []}),
            json.dumps({"next_id": 1}),
            json.dumps(_valid(next_id="3")),
            json.dumps(_valid(next_id=True)),
            json.dumps(_valid(next_id=0)),
            json.dumps(_valid(next_id=1.5)),
            json.dumps(_valid(tasks={})),
            json.dumps(_valid(tasks=["x"])),
            json.dumps(_valid(tasks=[{"id": 0, "title": "a", "done": False}])),
            json.dumps(_valid(tasks=[{"id": True, "title": "a", "done": False}])),
            json.dumps(_valid(tasks=[{"id": "1", "title": "a", "done": False}])),
            json.dumps(_valid(tasks=[{"title": "a", "done": False}])),
            json.dumps(_valid(tasks=[{"id": 1, "title": 5, "done": False}])),
            json.dumps(_valid(tasks=[{"id": 1, "done": False}])),
            json.dumps(_valid(tasks=[{"id": 1, "title": "a", "done": 1}])),
            json.dumps(_valid(tasks=[{"id": 1, "title": "a"}])),
            json.dumps(
                _valid(
                    tasks=[
                        {"id": 1, "title": "a", "done": False},
                        {"id": 1, "title": "b", "done": False},
                    ]
                )
            ),
            json.dumps(_valid(next_id=1)),
            json.dumps(_valid(next_id=2, tasks=[{"id": 5, "title": "a", "done": False}])),
            "[" * 200000,
            '{"next_id": ' + "9" * 5000 + ', "tasks": []}',
        ],
    )
    def test_corrupt_raises_and_file_unchanged(self, tmp_path: Path, content: str | bytes) -> None:
        path = tmp_path / "todo.json"
        original = _write(path, content)
        with pytest.raises(StorageError) as excinfo:
            storage.load(path)
        assert str(excinfo.value) == f"저장 파일을 읽을 수 없습니다: {path}"
        assert path.read_bytes() == original

    def test_directory_path_is_read_error(self, tmp_path: Path) -> None:
        with pytest.raises(StorageError) as excinfo:
            storage.load(tmp_path)
        assert str(excinfo.value) == f"저장 파일을 읽을 수 없습니다: {tmp_path}"

    def test_exists_oserror_is_read_error(self, tmp_path: Path) -> None:
        path = tmp_path / ("a" * 300)
        with pytest.raises(StorageError) as excinfo:
            storage.load(path)
        assert str(excinfo.value) == f"저장 파일을 읽을 수 없습니다: {path}"

    def test_exists_oserror_via_monkeypatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing_exists(self: Path) -> bool:
            raise PermissionError("접근 불가")

        monkeypatch.setattr(Path, "exists", failing_exists)
        path = tmp_path / "todo.json"
        with pytest.raises(StorageError) as excinfo:
            storage.load(path)
        assert str(excinfo.value) == f"저장 파일을 읽을 수 없습니다: {path}"


class TestSave:
    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        todo = TodoList(4, [Task(1, " 우유 사기 ", True), Task(3, "운동", False)])
        storage.save(path, todo)
        assert storage.load(path) == todo

    def test_format(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        storage.save(path, TodoList(2, [Task(1, "우유", False)]))
        text = path.read_text(encoding="utf-8")
        assert text.endswith("}\n")
        assert not text.endswith("\n\n")
        assert "우유" in text
        assert (
            text
            == json.dumps(
                {"next_id": 2, "tasks": [{"id": 1, "title": "우유", "done": False}]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

    def test_overwrites_and_leaves_no_temp_files(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        storage.save(path, TodoList())
        storage.save(path, TodoList(2, [Task(1, "a")]))
        assert storage.load(path).next_id == 2
        assert [p.name for p in tmp_path.iterdir()] == ["todo.json"]

    def test_relative_path_in_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        storage.save(Path("todo.json"), TodoList())
        assert (tmp_path / "todo.json").exists()

    def test_missing_parent_folder_is_write_error(self, tmp_path: Path) -> None:
        path = tmp_path / "no_such_dir" / "todo.json"
        with pytest.raises(StorageError) as excinfo:
            storage.save(path, TodoList())
        assert str(excinfo.value) == f"저장 파일을 쓸 수 없습니다: {path}"
        assert not path.parent.exists()

    def test_replace_failure_keeps_original_and_cleans_temp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "todo.json"
        original = _write(path, json.dumps({"next_id": 1, "tasks": []}))

        def failing_replace(src: object, dst: object) -> None:
            raise OSError("replace 실패")

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(StorageError) as excinfo:
            storage.save(path, TodoList(2, [Task(1, "a")]))
        assert str(excinfo.value) == f"저장 파일을 쓸 수 없습니다: {path}"
        assert path.read_bytes() == original
        assert [p.name for p in tmp_path.iterdir()] == ["todo.json"]

    def test_surrogate_title_is_write_error_and_keeps_original(self, tmp_path: Path) -> None:
        path = tmp_path / "todo.json"
        original = _write(path, json.dumps({"next_id": 1, "tasks": []}))
        with pytest.raises(StorageError) as excinfo:
            storage.save(path, TodoList(2, [Task(1, "\udcff")]))
        assert str(excinfo.value) == f"저장 파일을 쓸 수 없습니다: {path}"
        assert path.read_bytes() == original
        assert [p.name for p in tmp_path.iterdir()] == ["todo.json"]

    def test_non_oserror_cleans_temp_and_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "todo.json"

        def failing_replace(src: object, dst: object) -> None:
            raise RuntimeError("예상 밖 실패")

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(RuntimeError):
            storage.save(path, TodoList())
        assert list(tmp_path.iterdir()) == []
