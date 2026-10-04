"""todo 패키지가 던지는 예외. 메시지에 '오류: ' 접두어는 붙이지 않는다."""


class TodoError(Exception):
    """이 패키지 예외의 기반 클래스."""


class UsageError(TodoError):
    """명령이 없거나, 알 수 없는 명령이거나, 인자 개수가 틀릴 때."""

    def __init__(self) -> None:
        super().__init__('사용법: python -m todo add "<제목>" | list | done <번호> | delete <번호>')


class InvalidTitleError(TodoError):
    """제목 검증 실패. 메시지는 호출하는 쪽이 정한다."""


class TaskNotFoundError(TodoError):
    """번호에 해당하는 할 일이 없거나 번호가 숫자가 아닐 때."""

    def __init__(self, raw_id: str) -> None:
        super().__init__(f"#{raw_id} 할 일을 찾을 수 없습니다")
        self.raw_id = raw_id


class StorageError(TodoError):
    """저장 파일 읽기·쓰기 실패. 메시지는 호출하는 쪽이 정한다."""
