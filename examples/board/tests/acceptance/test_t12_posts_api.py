"""T-12 인수 테스트 (1/4): 목록·페이지·상세 (AC-11~16). HTTP 수준."""

import pytest

NOT_FOUND_MSG = "게시글을 찾을 수 없습니다."
BIG = "9" * 30


def test_ac11_empty_list(env):
    r = env.anon.get("/api/posts")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 10}


def test_ac12_anonymous_list_newest_first(env):
    ids = [env.post(title=f"t{i}")["id"] for i in range(5)]
    r = env.anon.get("/api/posts")
    assert r.status_code == 200
    body = r.json()
    assert [p["id"] for p in body["items"]] == ids[::-1]
    assert body["total"] == 5
    item = body["items"][0]
    assert set(item) == {"id", "title", "author", "created_at"}
    assert item["created_at"].endswith("Z")


def test_ac12_edit_does_not_change_order(env):
    a = env.post(title="first")
    b = env.post(title="second")
    r = env.alice.put(f"/api/posts/{a['id']}", json={"title": "x", "content": "y"})
    assert r.status_code == 200
    ids = [p["id"] for p in env.anon.get("/api/posts").json()["items"]]
    assert ids == [b["id"], a["id"]]


def test_ac13_ten_posts_one_page_eleven_two_pages(env):
    ids = env.fill(10)
    b = env.anon.get("/api/posts").json()
    assert len(b["items"]) == 10 and b["total"] == 10
    ids.append(env.post()["id"])
    p1 = env.anon.get("/api/posts?page=1").json()
    p2 = env.anon.get("/api/posts?page=2").json()
    assert len(p1["items"]) == 10 and p1["page"] == 1
    assert [p["id"] for p in p2["items"]] == [ids[0]] and p2["page"] == 2
    assert p2["total"] == 11 and p2["size"] == 10


@pytest.mark.parametrize("q", ["0", "-1", "-999", "abc", "", "1.5", "1e2", " 2", "+2", "٢", "-abc"])
def test_ac14_invalid_page_falls_back_to_page_1(env25, q):
    ids, page = env25.page_ids(env25.anon.get("/api/posts", params={"page": q}))
    assert page == 1
    assert ids == env25.ids[::-1][:10]


@pytest.mark.parametrize("q", ["4", "99", "1000000", "999999999", BIG])
def test_ac14_over_last_page_goes_to_last_page(env25, q):
    ids, page = env25.page_ids(env25.anon.get(f"/api/posts?page={q}"))
    assert page == 3
    assert ids == env25.ids[::-1][20:]


@pytest.mark.parametrize("q", ["-" + BIG, "-0000000002", "-5"])
def test_ac14_negative_goes_to_page_1(env25, q):
    _, page = env25.page_ids(env25.anon.get(f"/api/posts?page={q}"))
    assert page == 1


@pytest.mark.parametrize("q", ["0000000002", "02", "000000000000000000000002"])
def test_ac14_leading_zeros_are_numeric_value(env25, q):
    ids, page = env25.page_ids(env25.anon.get(f"/api/posts?page={q}"))
    assert page == 2
    assert ids == env25.ids[::-1][10:20]


def test_ac14_all_zeros_is_page_1(env25):
    _, page = env25.page_ids(env25.anon.get("/api/posts?page=0000"))
    assert page == 1


def test_ac14_extra_query_ignored_size_fixed(env25):
    r = env25.anon.get("/api/posts?page=2&size=1000&foo=bar")
    ids, page = env25.page_ids(r)
    assert page == 2 and len(ids) == 10 and r.json()["size"] == 10


def test_ac14_empty_db_any_page_is_page_1(env):
    r = env.anon.get("/api/posts?page=7")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 10}


def test_ac15_anonymous_detail(env):
    p = env.post(title="hello", content="line1\nline2")
    r = env.anon.get(f"/api/posts/{p['id']}")
    assert r.status_code == 200
    b = r.json()
    assert b["title"] == "hello" and b["content"] == "line1\nline2"
    assert b["author"]["username"] == "alice_01"
    assert b["created_at"].endswith("Z")
    assert set(b) == {"id", "title", "content", "author", "created_at"}
    assert set(b["author"]) == {"id", "username"}


@pytest.mark.parametrize(
    "pid",
    ["9999", "0", "-1", "abc", "01", "1.0", "9223372036854775807", "9223372036854775808", BIG],
)
def test_ac16_not_found_ids_get_404(env, pid):
    env.post()
    r = env.anon.get(f"/api/posts/{pid}")
    env.err(r, 404, "post_not_found")
    assert r.json()["error"]["message"] == NOT_FOUND_MSG


def test_ac16_leading_zero_id_is_not_the_post(env):
    p = env.post()
    env.err(env.anon.get(f"/api/posts/0{p['id']}"), 404, "post_not_found")
