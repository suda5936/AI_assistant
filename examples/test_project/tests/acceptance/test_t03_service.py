"""T-03 인수 테스트: service 모듈 함수 수준 (명세 AC-2,3,4,6,7,8,9)."""

import pytest
from todo import service
from todo.errors import InvalidTitleError, TaskNotFoundError
from todo.models import Task, TodoList


def _list_with(*titles: str) -> TodoList:
    todo = TodoList()
    for t in titles:
        service.add_task(todo, t)
    return todo


# AC-2
def test_ac2_ids_start_at_1_and_increment():
    todo = TodoList()
    a = service.add_task(todo, "우유 사기")
    b = service.add_task(todo, "운동")
    assert (a.id, b.id) == (1, 2)
    assert a.title == "우유 사기"
    assert a.done is False
    assert [t.id for t in todo.tasks] == [1, 2]


def test_ac2_deleted_id_is_not_reused():
    todo = _list_with("a", "b")
    service.delete_task(todo, "2")
    c = service.add_task(todo, "c")
    assert c.id == 3
    service.delete_task(todo, "1")
    service.delete_task(todo, "3")
    assert service.add_task(todo, "d").id == 4


# AC-3
@pytest.mark.parametrize("title", ["", " ", "   ", "\t", "\n", " \t\n "])
def test_ac3_blank_title_rejected_and_todo_unchanged(title):
    todo = _list_with("keep")
    with pytest.raises(InvalidTitleError) as ei:
        service.add_task(todo, title)
    assert str(ei.value) == "제목을 입력하세요"
    assert todo.next_id == 2
    assert [t.title for t in todo.tasks] == ["keep"]


def test_ac3_validate_title_blank():
    with pytest.raises(InvalidTitleError, match="제목을 입력하세요"):
        service.validate_title("")


# AC-4
def test_ac4_exactly_100_chars_allowed():
    todo = TodoList()
    task = service.add_task(todo, "가" * 100)
    assert len(task.title) == 100
    service.validate_title("a" * 100)


def test_ac4_101_chars_rejected_and_todo_unchanged():
    todo = TodoList()
    with pytest.raises(InvalidTitleError) as ei:
        service.add_task(todo, "a" * 101)
    assert str(ei.value) == "제목은 100자 이하여야 합니다"
    assert todo.next_id == 1
    assert todo.tasks == []


def test_ac4_whitespace_only_over_100_reports_empty_first():
    with pytest.raises(InvalidTitleError, match="제목을 입력하세요"):
        service.validate_title(" " * 150)


def test_ac4_long_title_with_padding_counts_all_chars():
    # 공백 포함 길이가 101이면 거부 (제목 trim 없음)
    with pytest.raises(InvalidTitleError, match="100자"):
        service.validate_title(" " + "a" * 100)


# AC-6
def test_ac6_list_tasks_sorted_ascending_new_list():
    todo = TodoList(
        next_id=6,
        tasks=[Task(5, "e"), Task(2, "b"), Task(4, "d", True)],
    )
    result = service.list_tasks(todo)
    assert [t.id for t in result] == [2, 4, 5]
    assert result is not todo.tasks
    assert [t.id for t in todo.tasks] == [5, 2, 4]


def test_ac6_list_tasks_empty():
    assert service.list_tasks(TodoList()) == []


# AC-7
def test_ac7_complete_marks_done_and_changed_true():
    todo = _list_with("a", "b")
    task, changed = service.complete_task(todo, "2")
    assert changed is True
    assert task.id == 2 and task.title == "b" and task.done is True
    assert todo.tasks[0].done is False
    assert todo.tasks[1].done is True


def test_ac7_complete_twice_changed_false_state_kept():
    todo = _list_with("a")
    service.complete_task(todo, "1")
    task, changed = service.complete_task(todo, "1")
    assert changed is False
    assert task.done is True
    assert todo.tasks[0].done is True


# AC-8
def test_ac8_delete_removes_and_returns_task():
    todo = _list_with("a", "b", "c")
    removed = service.delete_task(todo, "2")
    assert (removed.id, removed.title) == (2, "b")
    assert [t.id for t in todo.tasks] == [1, 3]
    assert todo.next_id == 4


def test_ac8_delete_same_twice_second_fails():
    todo = _list_with("a")
    service.delete_task(todo, "1")
    with pytest.raises(TaskNotFoundError):
        service.delete_task(todo, "1")


# AC-9
@pytest.mark.parametrize(
    "raw", ["99", "0", "abc", "-1", "1.5", "", " ", "1 ", " 1", "+1", "１", "1e0", "0x1"]
)
def test_ac9_invalid_or_missing_id_raises(raw):
    todo = _list_with("a")
    with pytest.raises(TaskNotFoundError) as ei:
        service.find_task(todo, raw)
    assert ei.value.raw_id == raw
    assert str(ei.value) == f"#{raw} 할 일을 찾을 수 없습니다"


@pytest.mark.parametrize("fn", [service.complete_task, service.delete_task])
def test_ac9_complete_and_delete_unknown_id_leave_todo_unchanged(fn):
    todo = _list_with("a", "b")
    with pytest.raises(TaskNotFoundError):
        fn(todo, "abc")
    with pytest.raises(TaskNotFoundError):
        fn(todo, "7")
    assert [(t.id, t.done) for t in todo.tasks] == [(1, False), (2, False)]
    assert todo.next_id == 3


def test_ac9_empty_list_any_id_not_found():
    with pytest.raises(TaskNotFoundError):
        service.find_task(TodoList(), "1")


def test_ac9_leading_zero_is_treated_as_number():
    todo = _list_with("a")
    assert service.find_task(todo, "01").id == 1
