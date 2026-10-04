# AI_assistant — 하네스 엔지니어링으로 만든 1인 AI 개발 회사

> 프롬프트 엔지니어링을 넘어 **하네스 엔지니어링**을 시도했습니다.
> 역할별 코딩 에이전트를 분리해 설계·구현·검증을 분업시키고, 따라야 할 규칙은 Agent Skill로 주었으며,
> 코드를 수정할 때마다 hook이 자동 검사해 그 결과를 에이전트에게 피드백으로 돌려주는 루프를 만들어
> AI가 생성한 코드를 자동 검증하는 개발 환경을 구현했습니다.

요구사항(자유 형식 명세서도 가능)을 주면, Claude Code 위에서 **PM · 아키텍트 · 개발자 · 리뷰어 · QA · 보안 리뷰어** 에이전트가 분업하고, **훅**이 매 단계를 기계적으로 검증해 배포 직전 수준의 서비스를 완성합니다.

## 실전 결과
| | 할 일 CLI (`test_project`) | 사내 게시판 웹 서비스 (`board`) |
|---|---|---|
| 입력 | 한 문단 요청 | 자유 형식 요청서 → PM이 AC 25개·질문 11개로 변환 |
| 구성 | Python CLI | FastAPI + SQLite + React/TS + Playwright |
| 에이전트 호출 | 20회 | 99회 (마일스톤 2개, 태스크 20개) |
| 리뷰·QA 반려 → 재작업 | 2회 | 8회 |
| 테스트 | 291개 | 백엔드 674 · 프론트 149 · E2E 42 (커버리지 99%) |
| 완료 기준 | 통과 | D1~D7 모두 통과 (깨끗한 클론 설치, E2E, 보안 리뷰, audit 포함) |

결과물과 산출 문서는 [`examples/`](examples/README.md)에 있습니다. board에서 하네스는 파일 수정 393회 중 28회를 즉시 되돌려 보냈고, "끝났다"는 선언을 9회 거부했으며, 역할 밖 행동을 22회 차단했습니다.

**에이전트가 하네스 자체의 결함을 찾아 보고**하기도 했습니다: 공통 린트 설정이 다른 위치에 클론하면 사라진다는 규칙 충돌(L-17), ESLint 9에서 편집 검사가 동작하지 않던 버그(L-19). 권한상 하네스를 직접 고치지 않고 대표에게 보고했고, 사람이 고쳤습니다. 개선 이력 21건은 [`docs/lessons.md`](docs/lessons.md)에 있습니다.

## 구조

```
AI_assistant/
├── CLAUDE.md                 회사 헌장: 조직도, 작업 순서, 절대 규칙 (PM이 항상 읽음)
├── ROADMAP.md                하네스 구축 로드맵과 완료 기준(D1~D7)
├── ruff.toml                 회사 공통 파이썬 린트 규칙 (coding-standards의 [자동] 규칙)
├── .claude/
│   ├── settings.json         훅 연결
│   ├── harness.json          역할별 권한표, 차단 명령, 검사 규칙, 품질 게이트 설정
│   ├── agents/               직원 6명 (PM은 메인 세션)
│   ├── skills/               규칙집 11개
│   └── hooks/                자동 검증 장치 6개
├── tests/                    훅이 잡아야 할 것을 잡는지 검증하는 테스트
├── scripts/harness_report.py 측정 리포트
├── docs/
│   ├── adr/                  회사 표준 스택 결정
│   └── lessons.md            실수 → 규칙 개선 기록
├── examples/                 실전 결과물 (test_project, board)
└── workplace/                실제 프로젝트 공간 (프로젝트마다 별도 git 저장소, 이 저장소에는 포함 안 됨)
```

### 역할 (Agents)
| 역할 | 하는 일 | 쓸 수 있는 곳 (훅이 강제) | 모델 |
|---|---|---|---|
| PM (메인 세션) | 명세, 작업 분배, STATUS, 최종 검수, 커밋 | `docs/00_request.md`, `01_spec.md`, `STATUS.md`, `README.md` | - |
| architect | 전체·마일스톤 설계, API 계약, ADR | `docs/02_design.md`, `docs/milestones/`, `docs/adr/` | opus |
| developer | 설계대로 구현 + 단위 테스트 | 코드 전체 (문서, 인수·E2E 테스트 제외), 커밋 불가 | sonnet |
| reviewer | 설계·규칙 기준 코드 리뷰, 통과/반려 | `docs/reviews/`, 셸 쓰기·커밋 불가 | opus |
| qa | **명세만 보고** 인수 테스트·E2E 작성·실행 | `docs/qa/`, `tests/acceptance/`, `tests/e2e/` | sonnet |
| security-reviewer | 인증·권한·인젝션·의존성 취약점 검토 | `docs/reviews/security-*` | opus |

### 규칙 (Skills)
| 스킬 | 내용 |
|---|---|
| `ship` | 전체 파이프라인: 규모 판단 → 명세 → 설계 → 태스크 루프 → 통합 검증 → 최종 검수 |
| `spec-writing` | 명세 템플릿, 검증 가능한 AC, 외부 명세서 변환, 마일스톤 분할, 놓치기 쉬운 상황 |
| `design-doc` | 전체 설계 + 마일스톤 설계, AC 추적표, 태스크 분할 |
| `coding-standards` | 파이썬 규칙. `[자동]`(훅이 검사) / `[판단]`(리뷰어가 검토) 구분 |
| `frontend-standards` | React + TypeScript 규칙 |
| `api-design` | API 계약 우선 설계, 오류 형식, 인증·권한, DB, 백엔드 계층 |
| `env-setup` | 표준 Makefile 명령 (`setup`, `check`, `dev`, `e2e`, `audit`, `coverage`) |
| `e2e-testing` | Playwright로 실제 서버·브라우저 시나리오 검증 |
| `review-checklist` | 리뷰·QA 판정 기준과 결과 문서 형식 |
| `security-checklist` | 보안 점검표 S1~S13 |
| `project-status` | STATUS 양식, 세션 재개 절차 |

### 자동 검증 (Hooks)
```
           ┌────────────── PreToolUse ──────────────┐
에이전트 ──▶ guard_write: 역할별 쓰기 권한 (권한표)      │──차단──▶ [HARNESS] 사유 → 에이전트가 다른 길을 찾음
도구 호출    guard_bash : 위험 명령, 역할별 셸 제한       │
           │ guard_read : qa의 구현 코드 읽기 금지 (독립 검증) │
           └─────────────────────────────────────────┘
               │ 통과
               ▼
           ┌────────────── PostToolUse ─────────────┐
           │ check_edit: 스택 감지 → ruff / prettier·eslint │──문제──▶ [HARNESS] 파일:줄 피드백 → 즉시 수정
           │   + 비밀값·파일 길이·TODO 형식·검사 끄기 금지  │   (포맷·import 정렬은 자동 교정)
           └─────────────────────────────────────────┘
               │
               ▼  "다 했다"
           ┌────────── Stop / SubagentStop ──────────┐
           │ quality_gate: 변경된 프로젝트 make check │──실패──▶ 끝낼 수 없음 → 계속 수정 (3회 후 사람에게)
           │   + 하네스 파일 변조 감지                │
           └─────────────────────────────────────────┘
SessionStart: session_start — 진행 중인 프로젝트의 STATUS 요약을 주입해 세션이 끊겨도 이어서 진행
```

핵심 설계: 3-1 관찰에서 **서브에이전트의 도구 호출에는 `agent_type`이 들어온다**는 것을 확인했고, 그래서 에이전트마다 훅을 따로 붙이지 않고 `harness.json`의 **권한표 하나**로 PM을 포함한 모든 역할의 권한을 관리합니다.

## 개발 흐름

```
대표: "/ship board <요청서>"
 PM ─ spec-writing ─▶ 01_spec.md (AC, 마일스톤, 질문) ──▶ ✋ 대표 승인
 architect ─────────▶ 02_design.md + milestones/M1.md (API 계약, AC 추적표, 태스크)
 마일스톤마다:
   태스크마다: developer ⇄ [훅] ─▶ reviewer ─반려─▶ developer … ─▶ qa ─▶ PM 커밋
   통합 검증: make check → qa(회귀 + E2E) → security-reviewer → audit → coverage
 PM ─ 최종 검수 (D1~D7을 명령으로 확인) ─▶ 대표에게 보고
```

## 사용법

```bash
git clone <이 저장소> && cd AI_assistant
claude                      # 처음 실행 시 작업 공간 신뢰(trust)를 승인해야 권한 설정이 적용됨
> /ship todo-app 터미널용 할 일 관리 프로그램을 만들어줘
> /ship board ./요청서.md   # 자유 형식 명세서도 가능
```

- 요구 도구: Python 3.11+, `ruff`, `pytest`, `make`, (서비스) Node 22, Playwright 브라우저
- 세션이 끊기면 다시 `claude`를 실행하면 됩니다. 시작 훅이 진행 중인 프로젝트를 알려주고 PM이 이어서 진행합니다.
- 에이전트나 스킬을 추가·수정한 뒤에는 **새 세션**을 시작해야 반영됩니다 (lessons L-04).
- 헤드리스 실행: `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 claude -p "/ship ..." --permission-mode acceptEdits --allowedTools Bash`
  (환경변수가 없으면 헤드리스 모드는 10분 넘게 걸리는 에이전트 작업을 기다리지 않고 종료합니다 — lessons L-16)

### 사람이 필요할 때 알림 받기
에이전트는 최대한 스스로 처리하고(도구 자동 설치 포함, `doctor` 스킬), **사람만 할 수 있는 일**만 알립니다.

| 알림이 오는 경우 | 예 |
|---|---|
| 결정·승인 | 명세 질문, 명세 승인, ADR, 3회 반려 |
| 관리자 권한 설치 | python, git, make, node 없음 (설치 명령 포함) |
| 권한 확인 창 | Claude Code가 도구 사용 허락을 기다림 |
| 진행 불가 | 품질 게이트 3회 연속 실패 |

| 채널 | 설정 | 언제 유용한가 |
|---|---|---|
| **바탕화면 알림** | 없음 (Windows 토스트 / Mac 알림 센터 / Linux notify-send) | 컴퓨터 앞에 있을 때 |
| **휴대폰 Claude 앱** | `./scripts/start.sh`로 시작 (Remote Control) | 자리를 비웠을 때. 앱에서 바로 답하고 승인 |
| 메일 (선택) | `.env`에 **발송용** 메일 계정 (알림 전용 계정 + 앱 비밀번호 권장) | 기록을 남기고 싶을 때 |

```bash
./scripts/start.sh                       # 휴대폰 앱과 연결된 세션으로 시작 (평소 이렇게)
python3 .claude/hooks/notify.py --test   # 알림 테스트 (desktop=sent 가 나오면 성공)
```
- 휴대폰: Claude 앱에 같은 계정으로 로그인 → Code 목록에서 이 세션 열기. 앱의 알림 권한을 켜 두세요.
- 메일 받는 주소는 `.claude/harness.json`의 `notify.to`입니다. 같은 결정 알림은 2시간, 권한 확인 창 알림은 2분 안에 다시 보내지 않습니다.

### 하네스 자체를 고칠 때 (관리자 모드)
에이전트는 `CLAUDE.md`, `.claude/`, `tests/` 등 하네스 영역을 수정할 수 없습니다 (훅이 차단, 셸 우회는 품질 게이트가 변조로 감지).
사람이 하네스를 고칠 때만 관리자 모드를 켭니다. 관리자 모드에서도 `workplace` 안에서는 역할 규칙이 그대로 적용됩니다.
```bash
touch ~/.claude/harness-admin    # 켜기 (에이전트는 이 명령을 실행할 수 없음)
rm ~/.claude/harness-admin       # 끄기
```

### 하네스 검증
```bash
python3 -m pytest -q             # 훅 테스트
python3 scripts/harness_report.py --project <이름>   # 측정 리포트
```

## 개선 기록
에이전트의 실수와 그것을 막은 규칙·훅은 [`docs/lessons.md`](docs/lessons.md)에 있습니다. 예:
- qa가 검사를 끄는 주석(`noqa`)을 3번 시도 → 훅이 차단 → qa가 코드를 고쳐 통과 (L-08)
- 단위 테스트가 놓친 출력 결함을 마일스톤 통합 검증이 실제 프로세스 실행으로 잡음 (L-09)
- 테스트의 가짜 `/tmp` 경로를 보안 규칙이 8번 오탐 → 규칙 조정 + 회귀 테스트 (L-06)

## 한계
- 판단이 필요한 품질(설계의 좋고 나쁨, UI의 미적 완성도)은 모델 능력과 대표의 승인 단계에 의존합니다.
- 셸 명령을 통한 우회는 패턴 기반으로만 막습니다. 마지막 방어선은 품질 게이트의 변조 감지와 git 기록입니다.
- 배포는 범위 밖입니다.
