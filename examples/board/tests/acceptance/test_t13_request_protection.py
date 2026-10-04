"""T-13 인수: 보안 응답 헤더, 문서 경로 404, CORS 미개방, OpenAPI 내보내기."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"
LIMIT = 65536
SECURITY = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}


def _assert_sec(headers):
    for k, v in SECURITY.items():
        assert headers.get(k) == v, (k, headers.get(k))


def test_t13_security_headers_on_all_response_kinds(server, cookie, padded):
    ck = [("Cookie", cookie)]
    te = [("Transfer-Encoding", "chunked")]
    cases = {
        "200 list": (200, server.get("/api/posts")),
        "201 post": (201, server.req("POST", "/api/posts", ck, padded(80, "hdr"))),
        "401": (401, server.get("/api/auth/me")),
        "404 route": (404, server.get("/api/nope")),
        "404 post": (404, server.get("/api/posts/999999")),
        "404 non-api": (404, server.get("/")),
        "405": (405, server.req("PATCH", "/api/posts", ck, b"{}")),
        "415": (415, server.req("POST", "/api/posts", body=b"x", ctype="text/plain")),
        "413": (413, server.req("POST", "/api/posts", body=padded(LIMIT + 1))),
        "411": (411, server.req("POST", "/api/posts", te, b"0\r\n\r\n", cl=False)),
        "422": (422, server.req("POST", "/api/posts", ck, b"{}")),
    }
    for name, (expected, (status, headers, _)) in cases.items():
        assert status == expected, (name, status)
        _assert_sec(headers)


@pytest.mark.parametrize(
    "path", ["/docs", "/redoc", "/openapi.json", "/api/docs", "/api/openapi.json"]
)
def test_t13_docs_paths_are_404(server, path):
    status, headers, _ = server.get(path)
    assert status == 404
    _assert_sec(headers)


def test_t13_cors_not_opened(server, cookie, padded):
    origin = [("Origin", "https://evil.example")]
    status, headers, _ = server.req(
        "OPTIONS",
        "/api/posts",
        [*origin, ("Access-Control-Request-Method", "POST")],
        ctype=None,
        cl=False,
    )
    assert status in (404, 405)
    assert not any(k.startswith("access-control-") for k in headers), headers
    status, headers, _ = server.get("/api/posts", origin)
    assert status == 200
    assert not any(k.startswith("access-control-") for k in headers), headers
    status, headers, _ = server.req(
        "POST", "/api/posts", [*origin, ("Cookie", cookie)], padded(80, "cors")
    )
    assert status == 201
    assert not any(k.startswith("access-control-") for k in headers), headers


def test_t13_openapi_export_works_with_docs_disabled(tmp_path):
    out = tmp_path / "openapi.json"
    r = subprocess.run(
        [sys.executable, "-m", "board.openapi_export", str(out)],
        cwd=BACKEND,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{tmp_path / 'x.db'}"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-800:]
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert "/api/posts" in spec["paths"]
    assert "/api/posts/{post_id}" in spec["paths"]
