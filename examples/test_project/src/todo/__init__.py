"""할 일 관리 CLI 패키지."""

import logging

# 라이브러리 관례: 로거 설정이 없을 때 Python 기본 핸들러(lastResort)가 경고를 표준 오류로
# 내보내지 않도록 한다. 사용자에게 보이는 출력은 cli.py만 담당한다.
logging.getLogger(__name__).addHandler(logging.NullHandler())
