# STATUS: board

- 현재 단계: 완료 (최종 검수 D1~D7 통과, 2026-10-04)
- 규모: 대 (근거: 새 서비스 프로젝트, 인증·DB·프론트엔드 포함)
- 마지막 갱신: 2026-10-04
- 규모 판단 근거: 새 서비스(인증·DB·프론트) → 대

## 마일스톤
| ID | 이름 | 상태 | 포함 AC |
|---|---|---|---|
| M1 | 회원가입·로그인 | 완료 (docs/history.md) | AC-1 ~ AC-10 |
| M2 | 게시글 | 완료 (docs/history.md) | AC-11 ~ AC-25 |

## 태스크 (M2)
- 완료. T-10~T-19 상세는 docs/history.md.

## 태스크 (최종 검수 중 발견)
| ID | 내용 | 상태 | 반려 횟수 | 최근 문서 |
|---|---|---|---|---|
| T-20 | D3 실패 보정: 백엔드 ruff 설정이 저장소 밖(/home/user/AI_assistant/ruff.toml)에만 있어 다른 위치 클론에서 `make check` 린트 43건 실패 → backend/pyproject.toml에 프로젝트 자체 [tool.ruff] 추가 | 완료 (커밋) | 1 | docs/reviews/T-20-r1.md (반려), T-20-r2.md (통과). ADR 0002 승인(PM 대행) 표기 정정 완료. | docs/reviews/T-20-r1.md (반려, Major 1: 02_design.md:51 충돌 — architect 담당). developer 완료(pyproject.toml만 수정, src=["."] 추가 판단 포함). 규모 중: developer → reviewer (근거: 설정 변경이 전체 린트에 영향) |

## 사용자 결정 대기
- (없음)

## 결정 기록
- 2026-10-04 ADR 0002(프로젝트 자체 ruff 설정, 루트 board/ruff.toml, src 미지정) PM 대행 승인: 표준 스택 범위 안, 새 도구·규칙 없음.
- 의존성 메이저 상향·표준 범위 안 ADR은 PM 대행 승인 (대표 지시). 표준을 벗어나는 결정만 STATUS에 적고 멈춘다. M1 결정은 docs/history.md.

## 열린 이슈
- [하네스, 대표 확인 필요] env-setup 스킬("[tool.ruff]를 만들지 말고 하네스 루트 ruff.toml을 물려받는다")과 회사 ruff.toml 주석(extend 권고)이 D3(깨끗한 클론)와 충돌 — 따르면 다른 위치 클론에서 make check 실패. board는 ADR 0002로 예외 처리(루트 board/ruff.toml). 다른 프로젝트에도 같은 문제가 생기므로 스킬·회사 설정 문구 수정 여부는 대표 결정(하네스 수정은 에이전트 권한 밖).
- [하네스, 대표 확인 필요] `.claude/hooks/check_edit.py:85`가 eslint에 `--format unix`를 넘기지만 ESLint 9에는 이 포매터가 없어 편집 훅의 eslint 검사가 동작하지 않음(`make check`는 영향 없음). PM 권한 밖이라 최종 보고에 포함.
  - 2026-10-04 T-19 developer도 같은 훅 경고 재확인("unix formatter is no longer part of core ESLint"). 해결안(훅 수정 또는 eslint-formatter-unix 설치)은 대표 결정 사항.
- [해소] `.env.example`: 보안 리뷰(M2)가 프론트 변수 포함 4개 변수 기재 확인.
- [프로세스] M1 T-07 QA가 구현 코드를 읽은 규칙 위반 1건(보고됨). 이후 QA 호출마다 "구현 코드 열람 금지" 명시.
- [M2 통합 검증 때] 프론트 인수 테스트(tests/acceptance/frontend)는 `make check`에 포함되지 않음 → 통합 검증에서 별도 실행. QA가 T-07 vitest.config include를 `t07_*.test.tsx`로 좁힘(포트 충돌 방지). 설정 파일: vitest.config.ts(T-07), vitest.t14~t18.config.ts(총 6개)를 각각 실행. 백엔드 pytest는 약 3분 걸려 타임아웃을 늘려야 함.
- [QA 한계, 통합 검증 때] QA 인수 t18에서 "저장 시점 403"(남의 글 폼 저장)은 화면 진입이 막혀 실서버로 재현 못 함(API는 직접 호출로 확인), "아무것도 안 바꾸고 저장" 케이스는 훅 300줄 제한으로 제외. 통합 E2E에서 보완 확인.
- M2로 이월: conftest 테이블 직접 나열, AuthProvider.test Minor 2건, 보안 Minor 3건(본문 크기 상한, 보안 헤더, M2 설계 조건: 이동 경로에 사용자 입력 금지·CORS 미개방).

## M2 통합 검증 진행
- 보안 리뷰: docs/reviews/security-M2-r1.md 통과 (Critical 0, Major 0, Minor 2: react-router 6.30.6 open redirect moderate—메이저 상향 필요·현재 악용 불가, vitest moderate—개발 도구). 이월 보안 항목 4개 해소.
- 최종 검수 D3: 클론 check 실패 → T-20(루트 ruff.toml)으로 보정, 재확인 통과.
- 최종 검수 결과(PM이 깨끗한 클론에서 실행): setup·check exit 0 / make e2e 42개 통과 / make audit exit 0(high 이상 없음, moderate 5건) / make coverage 백엔드 99.2%·프론트 lines 100% / 백엔드 674·프론트 149 통과.
- QA 통합 검증: docs/qa/M2-int-r1.md 통과 (AC 25/25, make e2e 42개). make coverage exit 0(PM 실행).
- 최종 검수 때 할 일: README 작성(설계 "배포" 절의 운영 보안 가정 4가지를 "운영 안내"로 옮김). react-router v7 상향은 다음 마일스톤/대표 판단 사항으로 보고.

## 다음 할 일
- 사용자 완료 보고. 대표 결정 사항: 하네스 이슈 2건(ruff 문구, eslint --format unix), react-router v7 상향.
