"""할 일 규칙: 제목 검증, 추가, 조회, 완료, 삭제. 입출력과 파일 접근은 하지 않는다."""

import re

from todo.errors import InvalidTitleError, TaskNotFoundError
from todo.models import Task, TodoList

MAX_TITLE_LENGTH: int = 100

_ID_PATTERN = re.compile(r"[0-9]+")


def validate_title(title: str) -> None:
    """제목이 비었거나 100자를 넘으면 InvalidTitleError를 던진다."""
    if title.strip() == "":
        raise InvalidTitleError("제목을 입력하세요")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidTitleError(f"제목은 {MAX_TITLE_LENGTH}자 이하여야 합니다")


def add_task(todo: TodoList, title: str) -> Task:
    """제목을 검증하고 새 할 일을 끝에 추가한 뒤 돌려준다."""
    validate_title(title)
    task = Task(id=todo.next_id, title=title, done=False)
    todo.tasks.append(task)
    todo.next_id += 1
    return task


def list_tasks(todo: TodoList) -> list[Task]:
    """id 오름차순으로 정렬한 새 리스트를 돌려준다."""
    return sorted(todo.tasks, key=lambda task: task.id)


def find_task(todo: TodoList, raw_id: str) -> Task:
    """입력 문자열 번호로 할 일을 찾는다. 없거나 형식이 틀리면 TaskNotFoundError."""
    if _ID_PATTERN.fullmatch(raw_id) is None:
        raise TaskNotFoundError(raw_id)
    try:
        task_id = int(raw_id)
    except ValueError:
        # 정수 자릿수 한도(4300자리)를 넘는 입력은 어떤 id와도 같을 수 없다.
        raise TaskNotFoundError(raw_id) from None
    for task in todo.tasks:
        if task.id == task_id:
            return task
    raise TaskNotFoundError(raw_id)


def complete_task(todo: TodoList, raw_id: str) -> tuple[Task, bool]:
    """할 일을 완료로 바꾼다. 이미 완료였으면 (task, False)를 돌려준다."""
    task = find_task(todo, raw_id)
    if task.done:
        return task, False
    task.done = True
    return task, True


def delete_task(todo: TodoList, raw_id: str) -> Task:
    """할 일을 목록에서 제거하고 돌려준다. next_id는 바꾸지 않는다."""
    task = find_task(todo, raw_id)
    todo.tasks.remove(task)
    return task
