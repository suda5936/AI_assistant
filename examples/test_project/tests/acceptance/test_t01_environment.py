"""T-01 인수 테스트: AC-1(실행 환경) + 설계 문서의 모델·예외 인터페이스."""

import dataclasses
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ac1_pyproject_python_311_and_no_runtime_deps():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "todo"
    assert project["requires-python"].replace(" ", "") == ">=3.11"
    assert project.get("dependencies", []) == []
    dev = " ".join(project["optional-dependencies"]["dev"])
    assert "pytest" in dev and "ruff" in dev


def test_ac1_package_importable_and_stdlib_only():
    import todo

    assert todo.__name__ == "todo"
    for name in ("models", "errors"):
        mod = __import__(f"todo.{name}", fromlist=["_"])
        src = Path(mod.__file__).read_text(encoding="utf-8")
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M)
        for imp in imports:
            top = imp.split(".")[0]
            assert top in sys.stdlib_module_names or top == "todo", imp


def test_ac1_makefile_targets_exist():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("setup", "check", "lint", "test", "run"):
        assert re.search(rf"^{target}\s*:", text, re.M), target


def test_ac1_env_example_documents_todo_file():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TODO_FILE" in text


def test_ac1_gitignore_covers_venv_and_todo_json():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    joined = "\n".join(lines)
    assert ".venv" in joined
    assert "__pycache__" in joined
    assert ".env" in joined


def test_ac1_acceptance_dir_has_no_init():
    assert not (ROOT / "tests" / "acceptance" / "__init__.py").exists()


def test_ac1_no_stray_todo_json_in_repo_root():
    assert not (ROOT / "todo.json").exists()


def test_models_defaults_match_design():
    from todo.models import Task, TodoList

    t = Task(id=1, title="a")
    assert t.done is False
    assert dataclasses.is_dataclass(Task) and dataclasses.is_dataclass(TodoList)
    a, b = TodoList(), TodoList()
    assert a.next_id == 1 and a.tasks == []
    a.tasks.append(t)
    assert b.tasks == []  # 인스턴스 간 리스트 공유 금지


def test_errors_hierarchy_and_messages():
    from todo import errors

    for cls in (
        errors.UsageError,
        errors.InvalidTitleError,
        errors.TaskNotFoundError,
        errors.StorageError,
    ):
        assert issubclass(cls, errors.TodoError)
    assert issubclass(errors.TodoError, Exception)

    e = errors.TaskNotFoundError("abc")
    assert e.raw_id == "abc"
    assert str(e) == "#abc 할 일을 찾을 수 없습니다"
    assert str(errors.TaskNotFoundError("")) == "# 할 일을 찾을 수 없습니다"
    assert str(errors.TaskNotFoundError("-1")) == "#-1 할 일을 찾을 수 없습니다"
    assert not str(e).startswith("오류")


def test_errors_message_passthrough():
    from todo.errors import InvalidTitleError, StorageError, UsageError

    assert str(InvalidTitleError("제목을 입력하세요")) == "제목을 입력하세요"
    msg = "저장 파일을 읽을 수 없습니다: todo.json"
    assert str(StorageError(msg)) == msg
    assert str(UsageError()) == (
        '사용법: python -m todo add "<제목>" | list | done <번호> | delete <번호>'
    )
