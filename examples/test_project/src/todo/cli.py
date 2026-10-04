"""명령줄 인터페이스: 인자 해석, 출력, 종료 코드."""

import sys
from collections.abc import Sequence
from pathlib import Path

from todo import service, storage
from todo.errors import StorageError, TodoError, UsageError
from todo.models import Task

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_STORAGE_ERROR = 2

# 명령별 필요한 인자 수
_ARG_COUNTS = {"add": 1, "list": 0, "done": 1, "delete": 1}


def format_task_line(task: Task) -> str:
    """목록 한 줄을 만든다."""
    mark = "x" if task.done else " "
    return f"#{task.id} [{mark}] {task.title}"


def _run_add(path: Path, title: str) -> None:
    service.validate_title(title)
    todo = storage.load(path)
    task = service.add_task(todo, title)
    storage.save(path, todo)
    print(f"추가됨: #{task.id} {task.title}")


def _run_list(path: Path) -> None:
    tasks = service.list_tasks(storage.load(path))
    if not tasks:
        print("할 일이 없습니다")
        return
    for task in tasks:
        print(format_task_line(task))


def _run_done(path: Path, raw_id: str) -> None:
    todo = storage.load(path)
    task, changed = service.complete_task(todo, raw_id)
    if not changed:
        print(f"이미 완료됨: #{task.id}")
        return
    storage.save(path, todo)
    print(f"완료: #{task.id} {task.title}")


def _run_delete(path: Path, raw_id: str) -> None:
    todo = storage.load(path)
    task = service.delete_task(todo, raw_id)
    storage.save(path, todo)
    print(f"삭제됨: #{task.id} {task.title}")


def _dispatch(args: Sequence[str]) -> None:
    """인자를 검사하고 명령을 실행한다. 실패하면 TodoError를 던진다."""
    if not args or args[0] not in _ARG_COUNTS:
        raise UsageError()
    command, params = args[0], args[1:]
    if len(params) != _ARG_COUNTS[command]:
        raise UsageError()
    path = storage.resolve_path()
    if command == "add":
        _run_add(path, params[0])
    elif command == "list":
        _run_list(path)
    elif command == "done":
        _run_done(path, params[0])
    else:
        _run_delete(path, params[0])


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 진입점. 종료 코드(0 성공, 1 입력 오류, 2 저장 파일 오류)를 반환한다."""
    args = sys.argv[1:] if argv is None else argv
    try:
        _dispatch(args)
    except StorageError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return EXIT_STORAGE_ERROR
    except TodoError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    return EXIT_OK
