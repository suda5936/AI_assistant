"""T-12 인수 테스트 (3/4): 수정·삭제·권한·판정 순서 (AC-20~22, 24, 25). HTTP 수준."""

import pytest

J = {"Content-Type": "application/json"}
SCRIPT = "<script>alert(1)</script>"


def test_ac21_author_can_edit_and_it_is_reflected(env):
    p = env.post(title="old", content="oldc")
    r = env.alice.put(f"/api/posts/{p['id']}", json={"title": "new", "content": "newc"})
    assert r.status_code == 200
    b = r.json()
    assert b["title"] == "new" and b["content"] == "newc"
    assert b["created_at"] == p["created_at"] and b["author"] == p["author"]
    assert b["id"] == p["id"]
    assert env.anon.get(f"/api/posts/{p['id']}").json() == b
    assert env.anon.get("/api/posts").json()["items"][0]["title"] == "new"
    assert len(env.rows()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "c"},
        {"title": "t", "content": "   "},
        {"title": "t"},
        {"content": "c"},
    ],
)
def test_ac21_invalid_edit_rejected_and_unchanged(env, payload):
    p = env.post(title="old", content="oldc")
    before = env.rows()
    env.err(env.alice.put(f"/api/posts/{p['id']}", json=payload), 422, "validation_error")
    assert env.rows() == before


def test_ac21_edit_nonexistent_is_404(env):
    r = env.alice.put("/api/posts/9999", json={"title": "t", "content": "c"})
    env.err(r, 404, "post_not_found")


def test_ac21_edit_twice_is_fine(env):
    p = env.post()
    for _ in range(2):
        r = env.alice.put(f"/api/posts/{p['id']}", json={"title": "same", "content": "same"})
        assert r.status_code == 200
    assert env.rows()[0][1] == "same"


def test_ac20_update_boundaries(env):
    p = env.post()
    url = f"/api/posts/{p['id']}"
    assert env.alice.put(url, json={"title": "a" * 100, "content": "b" * 5000}).status_code == 200
    env.err(env.alice.put(url, json={"title": "a" * 101, "content": "b"}), 422, "validation_error")
    env.err(env.alice.put(url, json={"title": "a", "content": "b" * 5001}), 422, "validation_error")
    row = env.rows()[0]
    assert len(row[1]) == 100 and len(row[2]) == 5000


def test_ac20_lone_surrogate_on_update_is_422_and_unchanged(env):
    p = env.post()
    before = env.rows()
    r = env.alice.put(
        f"/api/posts/{p['id']}", content='{"title": "\\ud800", "content": "c"}', headers=J
    )
    env.err(r, 422, "validation_error")
    assert env.rows() == before


def test_ac25_script_survives_edit(env):
    p = env.post()
    r = env.alice.put(f"/api/posts/{p['id']}", json={"title": SCRIPT, "content": SCRIPT})
    assert r.status_code == 200 and r.json()["title"] == SCRIPT
    assert env.rows()[0][2] == SCRIPT


def test_ac22_author_delete_then_gone(env):
    p = env.post()
    other = env.post(title="other")
    r = env.alice.delete(f"/api/posts/{p['id']}", json={})
    assert r.status_code == 204 and r.content == b""
    env.err(env.anon.get(f"/api/posts/{p['id']}"), 404, "post_not_found")
    assert [x["id"] for x in env.anon.get("/api/posts").json()["items"]] == [other["id"]]
    assert [row[0] for row in env.rows()] == [other["id"]]


def test_ac22_delete_twice_second_is_404(env):
    p = env.post()
    assert env.alice.delete(f"/api/posts/{p['id']}", json={}).status_code == 204
    env.err(env.alice.delete(f"/api/posts/{p['id']}", json={}), 404, "post_not_found")


@pytest.mark.parametrize("pid", ["9999", "abc", "0", "-1", "01", "9" * 30])
def test_ac22_delete_nonexistent_and_bad_ids_404(env, pid):
    env.err(env.alice.delete(f"/api/posts/{pid}", json={}), 404, "post_not_found")


def test_ac22_delete_requires_json_content_type(env):
    p = env.post()
    env.err(env.alice.delete(f"/api/posts/{p['id']}"), 415, "unsupported_media_type")
    assert len(env.rows()) == 1


def test_ac22_delete_on_page2_adjusts_list(env):
    ids = env.fill(11)
    assert env.alice.delete(f"/api/posts/{ids[0]}", json={}).status_code == 204
    b = env.anon.get("/api/posts?page=2").json()
    assert b["page"] == 1 and b["total"] == 10 and len(b["items"]) == 10


def test_ac24_anonymous_put_delete_401_db_unchanged(env):
    p = env.post()
    before = env.rows()
    r = env.anon.put(f"/api/posts/{p['id']}", json={"title": "x", "content": "y"})
    env.err(r, 401, "unauthenticated")
    env.err(env.anon.delete(f"/api/posts/{p['id']}", json={}), 401, "unauthenticated")
    assert env.rows() == before


def test_ac24_401_comes_before_422_and_404(env):
    env.err(
        env.anon.put("/api/posts/99999", json={"title": "", "content": ""}), 401, "unauthenticated"
    )
    env.err(env.anon.put("/api/posts/abc", json={"bad": 1}), 401, "unauthenticated")
    env.err(env.anon.delete("/api/posts/99999", json={}), 401, "unauthenticated")
    env.err(env.anon.delete("/api/posts/abc", json={}), 401, "unauthenticated")


def test_ac24_garbage_cookie_is_401(env):
    p = env.post()
    env.anon.cookies.set("board_session", "garbage")
    env.err(env.anon.delete(f"/api/posts/{p['id']}", json={}), 401, "unauthenticated")
    assert len(env.rows()) == 1


def test_ac24_other_user_put_403_and_db_unchanged(env):
    p = env.post(title="mine", content="mine-c")
    before = env.rows()
    r = env.bob.put(f"/api/posts/{p['id']}", json={"title": "hack", "content": "hack"})
    env.err(r, 403, "forbidden")
    assert env.rows() == before
    assert env.anon.get(f"/api/posts/{p['id']}").json()["title"] == "mine"


def test_ac24_other_user_delete_403_and_db_unchanged(env):
    p = env.post()
    before = env.rows()
    env.err(env.bob.delete(f"/api/posts/{p['id']}", json={}), 403, "forbidden")
    assert env.rows() == before


def test_ac24_order_422format_404_403_422content(env):
    p = env.post()
    before = env.rows()
    url = f"/api/posts/{p['id']}"
    env.err(env.bob.put(url, json={"title": "", "content": ""}), 403, "forbidden")
    env.err(env.bob.put(url, json={"title": "a" * 101, "content": "c"}), 403, "forbidden")
    env.err(
        env.bob.put("/api/posts/9999", json={"title": "", "content": ""}), 404, "post_not_found"
    )
    env.err(env.bob.put(url, json={"title": "t"}), 422, "validation_error")
    env.err(env.bob.put("/api/posts/9999", json={}), 422, "validation_error")
    assert env.rows() == before


def test_ac24_other_user_still_403_after_author_edit(env):
    p = env.post()
    env.alice.put(f"/api/posts/{p['id']}", json={"title": "a2", "content": "c2"})
    env.err(
        env.bob.put(f"/api/posts/{p['id']}", json={"title": "x", "content": "y"}), 403, "forbidden"
    )
    assert env.rows()[0][1] == "a2"
