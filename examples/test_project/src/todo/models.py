"""할 일 데이터 구조."""

from dataclasses import dataclass, field


@dataclass
class Task:
    """할 일 하나."""

    id: int
    title: str
    done: bool = False


@dataclass
class TodoList:
    """저장 파일 전체에 해당하는 할 일 목록."""

    next_id: int = 1
    tasks: list[Task] = field(default_factory=list)
