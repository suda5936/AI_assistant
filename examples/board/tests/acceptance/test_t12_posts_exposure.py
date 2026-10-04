"""T-12 인수 테스트 (4/4): 응답에 불필요한 정보가 없는지, 허용되지 않는 메서드."""


def test_no_sensitive_fields_in_any_post_response(env):
    p = env.post()
    bodies = [
        env.anon.get("/api/posts").text,
        env.anon.get(f"/api/posts/{p['id']}").text,
        env.alice.put(f"/api/posts/{p['id']}", json={"title": "t", "content": "c"}).text,
        env.alice.post("/api/posts", json={"title": "t2", "content": "c2"}).text,
    ]
    for t in bodies:
        low = t.lower()
        for bad in ("password", "hash", "scrypt", "token", "session", "email"):
            assert bad not in low, (bad, t)


def test_error_responses_have_no_internal_info(env):
    for r in (
        env.anon.get("/api/posts/abc"),
        env.bob.put("/api/posts/9999", json={"title": "", "content": ""}),
        env.alice.post("/api/posts", json={"title": 1}),
    ):
        low = r.text.lower()
        assert "traceback" not in low and "sqlalchemy" not in low and "sqlite" not in low
        assert set(r.json()) == {"error"}


def test_unsupported_methods_are_405(env):
    p = env.post()
    assert env.alice.patch(f"/api/posts/{p['id']}", json={}).status_code == 405
    assert env.alice.delete("/api/posts", json={}).status_code == 405
    assert env.alice.put("/api/posts", json={"title": "t", "content": "c"}).status_code == 405
