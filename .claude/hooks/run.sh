#!/usr/bin/env bash
# 하네스 훅 실행기.
#
# 운영체제마다 파이썬 실행 이름이 다르다. 특히 Windows의 python3 는
# Microsoft Store로 연결되는 가짜 실행 파일인 경우가 많아 훅이 실행되지 않는다 (lessons L-23).
# 실제로 동작하는 파이썬 3.11 이상을 찾아 훅 스크립트를 실행한다.
#
# 사용법 (settings.json): bash "$CLAUDE_PROJECT_DIR"/.claude/hooks/run.sh guard_write.py

script="${0%/*}/$1"  # dirname 없이 경로 계산 (최소 PATH에서도 동작)
shift

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 &&
    "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
    # Windows 한국어 콘솔(cp949)에서도 한글·기호가 깨지거나 오류 나지 않게 UTF-8로 고정
    PYTHONUTF8=1 PYTHONIOENCODING=utf-8 exec "$py" "$script" "$@"
  fi
done

echo "[HARNESS] 파이썬 3.11 이상을 찾지 못해 훅($script)을 실행하지 못했습니다. doctor 스킬로 점검하세요." >&2
exit 1
