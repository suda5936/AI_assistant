#!/usr/bin/env bash
# AI_assistant 하네스 실행.
#
#   ./scripts/start.sh          휴대폰 Claude 앱과 연결된 세션으로 시작 (Remote Control)
#   ./scripts/start.sh --local  이 컴퓨터에서만 쓰는 일반 세션으로 시작
#
# Remote Control로 시작하면 이 세션이 휴대폰 Claude 앱의 Code 목록에 나타나서,
# 자리를 비워도 앱에서 진행 상황을 보고 질문에 답하거나 승인할 수 있다.
# (작업은 계속 이 컴퓨터에서 실행되고, 훅·권한 규칙도 그대로 적용된다)
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v claude >/dev/null 2>&1; then
  echo "claude 명령을 찾을 수 없습니다. Claude Code를 설치하세요: https://claude.ai/code" >&2
  exit 1
fi

# Windows의 python3는 가짜 실행 파일일 수 있어 훅 실행기를 거친다 (lessons L-23)
bash .claude/hooks/run.sh doctor.py --brief || true

if [ "${1:-}" = "--local" ]; then
  exec claude
fi

echo "휴대폰 Claude 앱과 연결된 세션으로 시작합니다. (앱 > Code 에서 이 세션을 여세요)"
exec claude remote-control
