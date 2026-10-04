import pytest
from todo.errors import (
    InvalidTitleError,
    StorageError,
    TaskNotFoundError,
    TodoError,
    UsageError,
)
from todo.models import Task, TodoList


def test_usage_error_message():
    expected = '사용법: python -m todo add "<제목>" | list | done <번호> | delete <번호>'
    assert str(UsageError()) == expected


def test_task_not_found_message_and_raw_id():
    error = TaskNotFoundError("abc")
    assert str(error) == "#abc 할 일을 찾을 수 없습니다"
    assert error.raw_id == "abc"


def test_task_not_found_keeps_raw_input_as_is():
    assert str(TaskNotFoundError("01")) == "#01 할 일을 찾을 수 없습니다"
    assert str(TaskNotFoundError("")) == "# 할 일을 찾을 수 없습니다"


@pytest.mark.parametrize("message", ["제목을 입력하세요", "제목은 100자 이하여야 합니다"])
def test_invalid_title_error_keeps_message(message):
    assert str(InvalidTitleError(message)) == message


def test_storage_error_keeps_message():
    message = "저장 파일을 읽을 수 없습니다: todo.json"
    assert str(StorageError(message)) == message


@pytest.mark.parametrize(
    "error",
    [UsageError(), InvalidTitleError("x"), TaskNotFoundError("1"), StorageError("x")],
)
def test_all_errors_are_todo_error(error):
    assert isinstance(error, TodoError)


def test_models_defaults():
    todo = TodoList()
    assert todo.next_id == 1
    assert todo.tasks == []
    assert Task(id=1, title="a").done is False


def test_todo_list_default_tasks_not_shared():
    first, second = TodoList(), TodoList()
    first.tasks.append(Task(id=1, title="a"))
    assert second.tasks == []
