# 진행 기록

## M1 할 일 관리 기본 기능 (완료, AC-1 ~ AC-10)
| ID | 내용 | 반려 | 최종 문서 |
|---|---|---|---|
| T-01 | 환경 구성 + 모델·예외 | 0 | docs/qa/T-01-r1.md |
| T-02 | 저장소(storage) | 1 (리뷰 Major 2: exists() 예외 누수, 임시 파일 잔존) | docs/qa/T-02-r1.md |
| T-03 | 규칙(service) | 0 | docs/qa/T-03-r1.md |
| T-04 | CLI + __main__ | 0 | docs/qa/T-04-r1.md |
| T-05 | 통합 검증 반려 수정(로그가 stderr로 샘) | 0 | docs/qa/M1-int-r2.md |

- 통합 검증 1회차 반려(docs/qa/M1-int-r1.md): 손상 파일에서 stderr에 로그 한 줄이 추가됨 → T-05에서 NullHandler로 수정, 2회차 통과.
- 이월 Minor: T-04-r1 Minor 3건, T-05-r1 Minor(헬퍼 이름, storage 임시 파일 삭제 실패 로그 테스트, NullHandler 설계 문서 보충), 저장 후 권한 0600, storage.py의 RecursionError except 정리.
