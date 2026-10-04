---
name: doctor
description: 개발 도구 점검·자동 설치와 사람 승인 요청 절차. 필요한 도구(python, git, make, ruff, pytest, node, playwright 브라우저)가 있는지 확인하고, 자동으로 설치할 수 있는 것은 설치하고, 관리자 권한이 필요한 것은 대표에게 알림으로 요청한다. /ship 시작 전, 세션 시작 훅이 도구 누락을 알렸을 때, 명령이 'command not found'로 실패했을 때 사용한다.
---

# 도구 점검과 승인 요청

원칙: **에이전트가 할 수 있는 것은 끝까지 스스로 한다. 사람만 할 수 있는 것만 알림으로 요청한다.**

## 1. 점검
```bash
bash .claude/hooks/run.sh doctor.py            # CLI·파이썬 프로젝트
bash .claude/hooks/run.sh doctor.py --service  # 웹 서비스 (node, 브라우저 포함)
```

## 2. 자동 설치 (사람 승인 불필요)
관리자 권한 없이 사용자 영역에 설치되는 것은 바로 설치한다.
```bash
bash .claude/hooks/run.sh doctor.py --fix [--service]
```
- 대상: ruff, pytest (`pip install --user`), Playwright 브라우저
- 프로젝트 의존성(`make setup`의 `.venv`, `npm ci`의 `node_modules`)은 원래 developer가 설치한다.
- 설치 후 다시 점검해 해결됐는지 확인한다. `--user` 설치 후 명령을 못 찾으면 `python -m ruff`처럼 모듈로 실행한다.

## 3. 사람이 해야 하는 것 → 알림 요청
시스템 설치·관리자 권한(UAC, sudo)·PATH 변경이 필요한 도구(python, git, make, node)는 에이전트가 하지 않는다.
```bash
bash .claude/hooks/run.sh doctor.py --notify [--service]
```
- 대표에게 설치 명령이 담긴 알림이 간다.
- 진행 중인 프로젝트가 있으면 STATUS의 "사용자 결정 대기"에도 적는다 (알림이 다시 정리되어 간다).
- 그 도구가 없어도 할 수 있는 일(명세, 설계 등)은 계속 진행한다. 막히는 단계에서만 멈춘다.

## 4. 그 밖의 "사람만 할 수 있는 일" (알림)
아래는 훅이 자동으로 알림을 띄운다. PM은 STATUS의 "사용자 결정 대기"에 정확히 적기만 하면 된다.
| 상황 | 알림을 띄우는 것 |
|---|---|
| 명세 질문·승인, ADR 승인, 3회 반려 | PM이 STATUS "사용자 결정 대기"에 기록 → Stop 훅이 알림 |
| Claude Code가 권한 확인 창을 띄움 | Notification 훅이 알림 |
| 품질 게이트 3회 연속 실패 | 품질 게이트 훅이 알림 |
| 그 밖에 PM 판단으로 꼭 알려야 할 것 | `bash .claude/hooks/run.sh notify.py "<제목>" "<본문>"` |

알림은 바탕화면에 뜬다. 대표가 휴대폰 Claude 앱으로 세션을 연결했다면 앱에서 바로 답할 수 있다. 모든 알림은 `.harness/notifications.md`에도 남는다.

## STATUS에 쓰는 형식 (알림 본문이 된다)
```markdown
## 사용자 결정 대기
- [승인] 명세 Q1~Q3 답변 필요 — docs/01_spec.md "미해결 질문" (제안값 있음, "제안대로"로 답 가능)
- [설치] make 없음 — 관리자 권한 필요: winget install -e --id GnuWin32.Make
```
한 줄에 **무엇을, 어디서, 어떻게** 처리하면 되는지 쓴다. 대표는 알림만 보고 무엇을 해야 하는지 알 수 있어야 한다.
