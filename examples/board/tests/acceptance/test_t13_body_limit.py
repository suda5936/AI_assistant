"""T-13 인수: 본문 64 KiB 상한(413)과 판정 순서 415 -> 411/413 -> 라우터."""

import json

LIMIT = 65536


def test_t13_exact_limit_65536_is_accepted_and_created(server, cookie, padded):
    before = server.count("posts")
    status, _, body = server.req("POST", "/api/posts", [("Cookie", cookie)], padded(LIMIT, "exact"))
    assert status == 201, body[:300]
    assert server.count("posts") == before + 1


def test_t13_limit_plus_one_is_413_and_no_row(server, cookie, padded, code):
    before = server.count("posts")
    status, headers, body = server.req(
        "POST", "/api/posts", [("Cookie", cookie)], padded(LIMIT + 1, "over")
    )
    assert status == 413, body[:300]
    assert code(body) == "payload_too_large"
    assert headers["content-type"].startswith("application/json")
    assert server.count("posts") == before


def test_t13_413_for_70000_chars_but_422_for_5001_chars_under_limit(server, cookie, code):
    big = json.dumps({"title": "x", "content": "a" * 70000}).encode()
    assert server.req("POST", "/api/posts", [("Cookie", cookie)], big)[0] == 413
    small = json.dumps({"title": "x", "content": "a" * 5001}).encode()
    status, _, b = server.req("POST", "/api/posts", [("Cookie", cookie)], small)
    assert status == 422 and code(b) == "validation_error"


def test_t13_limit_applies_before_auth_and_to_signup_put_delete(server, cookie, padded):
    big = padded(LIMIT + 1)
    assert server.req("POST", "/api/posts", body=big)[0] == 413  # 비로그인도 413
    assert server.req("POST", "/api/users", body=big)[0] == 413
    assert server.req("PUT", "/api/posts/1", [("Cookie", cookie)], big)[0] == 413
    assert server.req("DELETE", "/api/posts/1", [("Cookie", cookie)], big)[0] == 413


def test_t13_get_is_not_limited(server):
    assert server.get("/api/posts")[0] == 200


def test_t13_empty_body_passes_limit_and_hits_router(server, cookie, code):
    status, _, body = server.req("POST", "/api/posts", [("Cookie", cookie)], b"")
    assert status == 422 and code(body) == "validation_error"


def test_t13_repeated_oversize_then_normal_request_still_works(server, cookie, padded):
    for _ in range(3):
        assert server.req("POST", "/api/posts", [("Cookie", cookie)], padded(LIMIT + 1))[0] == 413
    assert server.req("POST", "/api/posts", [("Cookie", cookie)], padded(100))[0] == 201


def test_t13_order_415_before_413(server, cookie, code):
    status, _, body = server.req(
        "POST", "/api/posts", [("Cookie", cookie)], b"x" * (LIMIT + 10), ctype="text/plain"
    )
    assert status == 415 and code(body) == "unsupported_media_type"


def test_t13_order_415_before_411(server, cookie, code):
    status, _, body = server.req(
        "POST",
        "/api/posts",
        [("Cookie", cookie), ("Transfer-Encoding", "chunked")],
        b"5\r\nhello\r\n0\r\n\r\n",
        ctype="text/plain",
        cl=False,
    )
    assert status == 415, body[:300]
    assert code(body) == "unsupported_media_type"


def test_t13_order_411_before_router_401_404(server, cookie):
    chunked = b"2\r\n{}\r\n0\r\n\r\n"
    te = [("Transfer-Encoding", "chunked")]
    assert server.req("POST", "/api/posts", te, chunked, cl=False)[0] == 411  # 라우터라면 401
    assert server.req("PUT", "/api/posts/999999", te, chunked, cl=False)[0] == 411
    assert server.req("DELETE", "/api/posts/999999", te, chunked, cl=False)[0] == 411
    # 정상 요청이면 라우터가 판정한다
    assert server.req("DELETE", "/api/posts/999999", [("Cookie", cookie)], b"{}")[0] == 404
    assert server.req("DELETE", "/api/posts/999999", body=b"{}")[0] == 401


def test_t13_normal_flow_unaffected(server):
    cred = json.dumps({"username": "flow_user_1", "password": "valid-pw-1"}).encode()
    assert server.req("POST", "/api/users", body=cred)[0] == 201
    status, headers, _ = server.req("POST", "/api/auth/login", body=cred)
    assert status == 200
    ck = [("Cookie", headers["set-cookie"].split(";")[0])]
    new = json.dumps({"title": "안녕", "content": "한글 본문\n둘째 줄"}).encode()
    status, _, body = server.req("POST", "/api/posts", ck, new)
    assert status == 201
    pid = json.loads(body)["id"]
    edited = json.dumps({"title": "수정", "content": "수정됨"}).encode()
    assert server.req("PUT", f"/api/posts/{pid}", ck, edited)[0] == 200
    status, _, body = server.get(f"/api/posts/{pid}")
    assert status == 200 and json.loads(body)["title"] == "수정"
    assert server.req("DELETE", f"/api/posts/{pid}", ck, b"{}")[0] == 204
    assert server.req("POST", "/api/auth/logout", ck, b"{}")[0] == 204
