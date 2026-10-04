"""OpenAPI 문서를 JSON 파일로 내보낸다 (make openapi)."""

import json
import sys
from pathlib import Path

from board.main import create_app


def main(argv: list[str] | None = None) -> int:
    """argv[0] 경로(부모 폴더 자동 생성)에 OpenAPI 문서를 JSON으로 쓴다. 성공 시 0."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("사용법: python -m board.openapi_export <출력 경로>")
    target = Path(args[0])
    target.parent.mkdir(parents=True, exist_ok=True)
    document = create_app().openapi()
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
