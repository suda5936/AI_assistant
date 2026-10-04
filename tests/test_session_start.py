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


# 세션이 작업 도중 꺼졌을 때 대비 (lessons L-25)
def agent_call(agent: str, description: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "session_id": "s1",
        "tool_input": {"subagent_type": agent, "description": description, "prompt": "..."},
    }


def test_interrupted_agent_is_reported_on_next_start(harness: Harness) -> None:
    harness.run("track_agents.py", agent_call("architect", "sheetmaker M1 설계"))
    harness.run("track_agents.py", agent_call("developer", "T-01 구현"))
    harness.run("track_agents.py", {"hook_event_name": "SubagentStop", "agent_type": "developer"})

    first = harness.run(
        "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"}
    )
    assert "도중 꺼졌습니다" in first.stdout
    assert "architect: sheetmaker M1 설계" in first.stdout
    assert "T-01" not in first.stdout  # 끝난 작업은 보고하지 않는다

    second = harness.run(
        "session_start.py", {"hook_event_name": "SessionStart", "source": "resume"}
    )
    assert "도중 꺼졌습니다" not in second.stdout  # 한 번 알리면 기록을 비운다


def test_compact_does_not_report_running_agents(harness: Harness) -> None:
    """같은 프로세스 안의 compact 에서는 백그라운드 에이전트가 아직 돌고 있을 수 있다."""
    harness.run("track_agents.py", agent_call("architect", "설계"))
    result = harness.run(
        "session_start.py", {"hook_event_name": "SessionStart", "source": "compact"}
    )
    assert "도중 꺼졌습니다" not in result.stdout


def test_uncommitted_changes_are_shown(harness: Harness) -> None:
    harness.git_init("workplace/shop")
    harness.write("workplace/shop/STATUS.md", "# STATUS: shop\n\n- 현재 단계: M1 구현\n")
    harness.write("workplace/shop/src/app.py", "x = 1\n")
    result = harness.run(
        "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"}
    )
    assert "커밋되지 않은 변경" in result.stdout
    assert "src/" in result.stdout
