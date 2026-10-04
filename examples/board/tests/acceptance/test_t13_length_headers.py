"""T-13 인수: Transfer-Encoding / Content-Length 처리(411, 우회 방지)."""

import json

import pytest


def _chunked(payload: bytes) -> bytes:
    return f"{len(payload):x}\r\n".encode() + payload + b"\r\n0\r\n\r\n"


def _signup(name: str) -> bytes:
    return json.dumps({"username": name, "password": "valid-pw-1"}).encode()


def test_t13_chunked_only_is_411(server, cookie, code):
    before = server.count("posts")
    status, _, body = server.req(
        "POST",
        "/api/posts",
        [("Cookie", cookie), ("Transfer-Encoding", "chunked")],
        _chunked(b'{"title":"c","content":"c"}'),
        cl=False,
    )
    assert status == 411, body[:300]
    assert code(body) == "length_required"
    assert server.count("posts") == before


def test_t13_content_length_plus_chunked_is_411_and_user_not_created(server, code):
    before = server.count("users")
    status, _, body = server.req(
        "POST",
        "/api/users",
        [("Content-Length", "10"), ("Transfer-Encoding", "chunked")],
        _chunked(_signup("smuggle_01")),
        cl=False,
    )
    assert status == 411, body[:300]
    assert code(body) == "length_required"
    assert server.count("users") == before


def test_t13_cl_plus_te_with_2mb_body_cannot_bypass_limit(server):
    """상한 우회 회귀: CL=10 + TE=chunked + 2MB 본문으로 가입이 되면 안 된다."""
    payload = json.dumps(
        {"username": "bigsmug_01", "password": "valid-pw-1", "pad": "a" * (2 * 1024 * 1024)}
    ).encode()
    before = server.count("users")
    status, _, body = server.req(
        "POST",
        "/api/users",
        [("Content-Length", "10"), ("Transfer-Encoding", "chunked")],
        _chunked(payload),
        cl=False,
    )
    assert status in (411, 413), (status, body[:200])
    assert server.count("users") == before


def test_t13_transfer_encoding_identity_with_content_length_is_411(server, code):
    before = server.count("users")
    status, _, body = server.req(
        "POST", "/api/users", [("Transfer-Encoding", "identity")], _signup("ident_01")
    )
    # 실제 서버(uvicorn)는 chunked 이외의 Transfer-Encoding을 자체 400으로 거부할 수 있다.
    assert status in (400, 411), body[:300]
    if status == 411:
        assert code(body) == "length_required"
    assert server.count("users") == before


def _raw_post(server, cl_lines, body=b"0123456789"):
    head = (
        "POST /api/users HTTP/1.1\r\nHost: x\r\nConnection: close\r\n"
        "Content-Type: application/json\r\n" + "".join(f"Content-Length: {v}\r\n" for v in cl_lines)
    )
    return server.raw(head.encode() + b"\r\n" + body)


def test_t13_conflicting_content_length_is_rejected(server, code):
    status, _, body = _raw_post(server, ["10", "5"])
    # 서버가 값이 다른 중복 헤더를 먼저 400으로 거부할 수 있다.
    assert status in (400, 411), (status, body[:200])
    if status == 411:
        assert code(body) == "length_required"


def test_t13_identical_duplicate_content_length_never_creates_user(server):
    # 서버가 동일 값 중복을 하나로 합쳐 앱에 넘길 수 있다(길이가 확정되므로 우회 불가).
    before = server.count("users")
    status, _, body = _raw_post(server, ["10", "10"])
    assert status in (400, 411, 422), (status, body[:200])
    assert server.count("users") == before


@pytest.mark.parametrize("value", ["abc", "-5", "1e3", "+10", "0x10"])
def test_t13_non_numeric_content_length_is_411_or_rejected(server, code, value):
    try:
        status, _, body = _raw_post(server, [value])
    except AssertionError:
        return  # 서버가 응답 없이 연결을 끊음: 처리되지 않았으므로 허용
    assert status in (400, 411), (status, body[:200])
    if status == 411:
        assert code(body) == "length_required"


def test_t13_huge_digit_content_length_is_413_or_rejected_not_500(server, code):
    status, _, body = _raw_post(server, ["9" * 5000], body=b"")
    # 서버(파서)가 먼저 400으로 거부할 수 있다. 500은 안 된다.
    assert status in (400, 413), (status, body[:200])
    if status == 413:
        assert code(body) == "payload_too_large"


def test_t13_leading_zero_content_length_is_not_rejected(server):
    payload = _signup("zero_pad_01")
    status, _, body = _raw_post(server, ["0" * 5000 + str(len(payload))], body=payload)
    assert status not in (411, 413, 500), (status, body[:200])
