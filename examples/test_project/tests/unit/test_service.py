"""service 모듈 단위 테스트."""

import pytest
from todo import service
from todo.errors import InvalidTitleError, TaskNotFoundError
from todo.models import Task, TodoList


def make_todo() -> TodoList:
    """id 1(완료), 3(미완료)이 있고 next_id가 4인 목록."""
    return TodoList(next_id=4, tasks=[Task(1, "우유", True), Task(3, "운동", False)])


class TestValidateTitle:
    def test_accepts_normal_title(self) -> None:
        service.validate_title("우유 사기")

    def test_accepts_100_chars(self) -> None:
        service.validate_title("가" * 100)

    def test_rejects_101_chars(self) -> None:
        with pytest.raises(InvalidTitleError) as info:
            service.validate_title("가" * 101)
        assert str(info.value) == "제목은 100자 이하여야 합니다"

    @pytest.mark.parametrize("title", ["", "   ", "\t\n"])
    def test_rejects_blank(self, title: str) -> None:
        with pytest.raises(InvalidTitleError) as info:
            service.validate_title(title)
        assert str(info.value) == "제목을 입력하세요"

    def test_blank_check_comes_first(self) -> None:
        with pytest.raises(InvalidTitleError) as info:
            service.validate_title(" " * 101)
        assert str(info.value) == "제목을 입력하세요"

    def test_does_not_check_encoding(self) -> None:
        service.validate_title("\udcff")


class TestAddTask:
    def test_ids_increase_from_one(self) -> None:
        todo = TodoList()
        first = service.add_task(todo, "a")
        second = service.add_task(todo, "b")
        assert (first.id, second.id) == (1, 2)
        assert todo.next_id == 3
        assert todo.tasks == [first, second]
        assert first.done is False

    def test_keeps_title_as_is(self) -> None:
        todo = TodoList()
        task = service.add_task(todo, "  공백  ")
        assert task.title == "  공백  "

    def test_does_not_reuse_deleted_id(self) -> None:
        todo = TodoList()
        service.add_task(todo, "a")
        service.add_task(todo, "b")
        service.delete_task(todo, "2")
        assert service.add_task(todo, "c").id == 3

    def test_invalid_title_leaves_todo_unchanged(self) -> None:
        todo = make_todo()
        with pytest.raises(InvalidTitleError):
            service.add_task(todo, "  ")
        assert todo == make_todo()


class TestListTasks:
    def test_empty(self) -> None:
        assert service.list_tasks(TodoList()) == []

    def test_sorted_by_id_without_changing_original(self) -> None:
        todo = TodoList(next_id=4, tasks=[Task(3, "c"), Task(1, "a"), Task(2, "b")])
        result = service.list_tasks(todo)
        assert [task.id for task in result] == [1, 2, 3]
        assert [task.id for task in todo.tasks] == [3, 1, 2]
        assert result is not todo.tasks


class TestFindTask:
    def test_finds_by_id(self) -> None:
        assert service.find_task(make_todo(), "3").title == "운동"

    def test_leading_zero_is_same_id(self) -> None:
        assert service.find_task(make_todo(), "01").id == 1

    @pytest.mark.parametrize(
        "raw_id", ["2", "0", "abc", "-1", "1.5", "", " 1", "1 ", "1\n", "+1", "１", "9" * 5000]
    )
    def test_not_found(self, raw_id: str) -> None:
        with pytest.raises(TaskNotFoundError) as info:
            service.find_task(make_todo(), raw_id)
        assert info.value.raw_id == raw_id
        assert str(info.value) == f"#{raw_id} 할 일을 찾을 수 없습니다"


class TestCompleteTask:
    def test_marks_done(self) -> None:
        todo = make_todo()
        task, changed = service.complete_task(todo, "3")
        assert changed is True
        assert task.done is True
        assert todo.tasks[1].done is True

    def test_already_done_is_not_changed(self) -> None:
        todo = make_todo()
        task, changed = service.complete_task(todo, "1")
        assert changed is False
        assert task.done is True
        assert todo == make_todo()

    def test_not_found(self) -> None:
        todo = make_todo()
        with pytest.raises(TaskNotFoundError):
            service.complete_task(todo, "2")
        assert todo == make_todo()


class TestDeleteTask:
    def test_removes_and_keeps_next_id(self) -> None:
        todo = make_todo()
        task = service.delete_task(todo, "3")
        assert task.title == "운동"
        assert [t.id for t in todo.tasks] == [1]
        assert todo.next_id == 4

    def test_not_found(self) -> None:
        todo = make_todo()
        with pytest.raises(TaskNotFoundError):
            service.delete_task(todo, "abc")
        assert todo == make_todo()
