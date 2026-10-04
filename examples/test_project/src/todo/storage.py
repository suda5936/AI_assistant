"""저장 경로 결정과 JSON 파일 읽기·쓰기. 출력은 하지 않고 로그만 남긴다."""

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from todo.errors import StorageError
from todo.models import Task, TodoList

logger = logging.getLogger(__name__)

ENV_VAR: str = "TODO_FILE"
DEFAULT_FILE_NAME: str = "todo.json"


def resolve_path(environ: Mapping[str, str] | None = None) -> Path:
    """저장 파일 경로를 정한다. 환경변수 TODO_FILE이 비어 있지 않으면 그 값을 쓴다."""
    env = os.environ if environ is None else environ
    value = env.get(ENV_VAR)
    if value:
        return Path(value)
    return Path(DEFAULT_FILE_NAME)


def load(path: Path) -> TodoList:
    """저장 파일을 읽어 TodoList를 돌려준다. 파일이 없으면 빈 목록이다.

    Raises:
        StorageError: 파일을 읽을 수 없거나 내용이 손상되었을 때.
    """
    try:
        if not path.exists():
            return TodoList()
        text = path.read_text(encoding="utf-8")
        raw = _parse_json(text)
        return _from_dict(raw)
    except (OSError, ValueError, RecursionError) as exc:
        logger.warning("저장 파일 읽기 실패: %s (%s)", path, exc)
        raise StorageError(f"저장 파일을 읽을 수 없습니다: {path}") from exc


def _parse_json(text: str) -> Any:
    """JSON 문자열을 해석한다. 너무 깊은 중첩(RecursionError)은 ValueError로 바꾼다."""
    try:
        return json.loads(text)
    except RecursionError as exc:
        raise ValueError("JSON이 너무 깊게 중첩됨") from exc


def save(path: Path, todo: TodoList) -> None:
    """TodoList를 임시 파일에 쓴 뒤 os.replace로 바꿔치기해 저장한다.

    Raises:
        StorageError: 쓰기 중 OSError가 났거나 UTF-8로 인코딩할 수 없을 때. 기존 파일은 유지된다.
    """
    text = json.dumps(_to_dict(todo), ensure_ascii=False, indent=2) + "\n"
    try:
        payload = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        logger.warning("저장 파일 인코딩 실패: %s (%s)", path, exc)
        raise StorageError(f"저장 파일을 쓸 수 없습니다: {path}") from exc

    temp_name: str | None = None
    replaced = False
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp_file:
            temp_name = temp_file.name
            temp_file.write(payload)
        os.replace(temp_name, path)
        replaced = True
    except OSError as exc:
        logger.warning("저장 파일 쓰기 실패: %s (%s)", path, exc)
        raise StorageError(f"저장 파일을 쓸 수 없습니다: {path}") from exc
    finally:
        if temp_name is not None and not replaced:
            _remove_quietly(temp_name)


def _remove_quietly(temp_name: str) -> None:
    """임시 파일을 지운다. 이미 없거나 지울 수 없어도 원래 오류를 가리지 않는다."""
    try:
        os.remove(temp_name)
    except OSError as exc:
        logger.warning("임시 파일 삭제 실패: %s (%s)", temp_name, exc)


def _is_int(value: Any) -> bool:
    """bool을 제외한 int인지 확인한다."""
    return isinstance(value, int) and not isinstance(value, bool)


def _from_dict(raw: Any) -> TodoList:
    """파싱된 JSON을 검증해 TodoList로 바꾼다. 손상되었으면 ValueError."""
    if not isinstance(raw, dict) or "next_id" not in raw or "tasks" not in raw:
        raise ValueError("최상위 구조가 올바르지 않음")
    next_id = raw["next_id"]
    if not _is_int(next_id) or next_id < 1:
        raise ValueError("next_id가 올바르지 않음")
    if not isinstance(raw["tasks"], list):
        raise ValueError("tasks가 리스트가 아님")

    tasks: list[Task] = []
    seen_ids: set[int] = set()
    for item in raw["tasks"]:
        task = _task_from_dict(item)
        if task.id in seen_ids:
            raise ValueError(f"id 중복: {task.id}")
        seen_ids.add(task.id)
        tasks.append(task)
    if seen_ids and next_id <= max(seen_ids):
        raise ValueError("next_id가 가장 큰 id 이하")
    return TodoList(next_id=next_id, tasks=tasks)


def _task_from_dict(item: Any) -> Task:
    """할 일 항목 하나를 검증해 Task로 바꾼다. 손상되었으면 ValueError."""
    if not isinstance(item, dict):
        raise ValueError("할 일 항목이 객체가 아님")
    task_id = item.get("id")
    title = item.get("title")
    done = item.get("done")
    if not _is_int(task_id) or task_id < 1:
        raise ValueError("id가 올바르지 않음")
    if not isinstance(title, str):
        raise ValueError("title이 문자열이 아님")
    if not isinstance(done, bool):
        raise ValueError("done이 bool이 아님")
    return Task(id=task_id, title=title, done=done)


def _to_dict(todo: TodoList) -> dict[str, Any]:
    """TodoList를 저장 형식의 dict로 바꾼다."""
    return {
        "next_id": todo.next_id,
        "tasks": [{"id": t.id, "title": t.title, "done": t.done} for t in todo.tasks],
    }
