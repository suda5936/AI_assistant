"""세션 시작 훅(session_start) 테스트."""

from __future__ import annotations

from conftest import Harness

STATUS = """# STATUS: shop

- 현재 단계: M1 구현
- 규모: 대 (근거: 새 서비스)

## 마일스톤
| ID | 이름 | 상태 |
| M1 | 로그인 | 진행 |

## 태스크 (현재 마일스톤)
| T-01 | 환경 구성 | 완료 |
| T-02 | 회원가입 | 리뷰 반려 |

## 다음 할 일
- developer에게 T-02 수정 요청
"""


def test_active_project_is_summarized(harness: Harness) -> None:
    harness.write("workplace/shop/STATUS.md", STATUS)
    result = harness.run("session_start.py", {"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    assert "workplace/shop/STATUS.md" in result.stdout
    assert "현재 단계: M1 구현" in result.stdout
    assert "T-02 수정 요청" in result.stdout
    assert "환경 구성" not in result.stdout  # 태스크 표는 생략


def test_finished_projects_are_skipped(harness: Harness) -> None:
    harness.write("workplace/done/STATUS.md", STATUS.replace("M1 구현", "완료"))
    result = harness.run("session_start.py", {"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    assert result.stdout == ""
