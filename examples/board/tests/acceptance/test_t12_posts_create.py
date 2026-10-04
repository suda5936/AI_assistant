"""T-12 인수 테스트 (2/4): 작성 (AC-17~20, 25). HTTP 수준."""

import pytest

J = {"Content-Type": "application/json"}
SCRIPT = "<script>alert(1)</script>"


def test_ac17_anonymous_create_is_401_and_no_row(env):
    r = env.anon.post("/api/posts", json={"title": "t", "content": "c"})
    env.err(r, 401, "unauthenticated")
    assert env.rows() == []


def test_ac18_create_returns_post_with_author(env):
    r = env.alice.post("/api/posts", json={"title": "제목", "content": "내용\n둘째 줄"})
    assert r.status_code == 201
    b = r.json()
    assert b["author"]["username"] == "alice_01"
    assert b["title"] == "제목" and b["content"] == "내용\n둘째 줄"
    assert env.anon.get(f"/api/posts/{b['id']}").json() == b
    rows = env.rows()
    assert len(rows) == 1 and rows[0][3] == b["author"]["id"]


def test_ac18_client_cannot_set_author_or_id(env):
    me = env.alice.get("/api/auth/me").json()
    r = env.alice.post(
        "/api/posts",
        json={"title": "t", "content": "c", "author_id": 999, "id": 777, "created_at": "2000"},
    )
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        b = r.json()
        assert b["author"]["id"] == me["id"] and b["id"] != 777


def test_ac18_two_users_posts_have_own_authors(env):
    a = env.post(env.alice)
    b = env.post(env.bob)
    assert a["author"]["username"] == "alice_01" and b["author"]["username"] == "bobby_01"


def test_ac18_requires_json_content_type(env):
    r = env.alice.post(
        "/api/posts", content='{"title":"t","content":"c"}', headers={"Content-Type": "text/plain"}
    )
    env.err(r, 415, "unsupported_media_type")
    assert env.rows() == []


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"title": "", "content": "c"}, "title"),
        ({"title": "   ", "content": "c"}, "title"),
        ({"title": "\n\t ", "content": "c"}, "title"),
        ({"title": "　", "content": "c"}, "title"),
        ({"title": "t", "content": ""}, "content"),
        ({"title": "t", "content": "  \n "}, "content"),
    ],
)
def test_ac19_empty_or_blank_rejected_on_create(env, payload, field):
    r = env.alice.post("/api/posts", json=payload)
    env.err(r, 422, "validation_error")
    assert field in [d["field"] for d in r.json()["error"]["details"]]
    assert env.rows() == []


def test_ac19_both_empty_reports_both_fields_title_first(env):
    r = env.alice.post("/api/posts", json={"title": "", "content": ""})
    env.err(r, 422, "validation_error")
    d = r.json()["error"]["details"]
    assert [x["field"] for x in d] == ["title", "content"]
    assert d[0]["message"] == "제목을 입력해 주세요."
    assert d[1]["message"] == "내용을 입력해 주세요."


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "t"},
        {"content": "c"},
        {"title": None, "content": "c"},
        {"title": 1, "content": "c"},
        {"title": "t", "content": ["x"]},
        [],
    ],
)
def test_ac19_missing_or_wrong_type_is_422(env, payload):
    env.err(env.alice.post("/api/posts", json=payload), 422, "validation_error")
    assert env.rows() == []


def test_ac19_malformed_json_is_422(env):
    env.err(env.alice.post("/api/posts", content="{bad", headers=J), 422, "validation_error")
    assert env.rows() == []


def test_ac20_title_100_ok_101_rejected(env):
    assert (
        env.alice.post("/api/posts", json={"title": "가" * 100, "content": "c"}).status_code == 201
    )
    r = env.alice.post("/api/posts", json={"title": "가" * 101, "content": "c"})
    env.err(r, 422, "validation_error")
    assert r.json()["error"]["details"][0] == {
        "field": "title",
        "message": "제목은 100자 이하여야 합니다.",
    }
    assert len(env.rows()) == 1 and len(env.rows()[0][1]) == 100


def test_ac20_content_5000_ok_5001_rejected(env):
    assert (
        env.alice.post("/api/posts", json={"title": "t", "content": "a" * 5000}).status_code == 201
    )
    r = env.alice.post("/api/posts", json={"title": "t", "content": "a" * 5001})
    env.err(r, 422, "validation_error")
    assert r.json()["error"]["details"][0] == {
        "field": "content",
        "message": "내용은 5000자 이하여야 합니다.",
    }
    assert len(env.rows()) == 1


def test_ac20_length_counts_code_points_not_bytes(env):
    ok = env.alice.post("/api/posts", json={"title": "😀" * 100, "content": "😀" * 5000})
    assert ok.status_code == 201
    r = env.alice.post("/api/posts", json={"title": "😀" * 101, "content": "c"})
    env.err(r, 422, "validation_error")


def test_ac20_whitespace_counts_and_is_preserved(env):
    t = "  " + "a" * 96 + "  "
    r = env.alice.post("/api/posts", json={"title": t, "content": "  c  \n"})
    assert r.status_code == 201
    assert r.json()["title"] == t and r.json()["content"] == "  c  \n"


@pytest.mark.parametrize(
    "body",
    ['{"title": "\\ud800", "content": "c"}', '{"title": "t", "content": "a\\udc00b"}'],
)
def test_ac20_lone_surrogate_is_422_not_500(env, body):
    env.err(env.alice.post("/api/posts", content=body, headers=J), 422, "validation_error")
    assert env.rows() == []


def test_ac20_valid_surrogate_pair_is_saved(env):
    r = env.alice.post(
        "/api/posts", content='{"title": "\\ud83d\\ude00", "content": "c"}', headers=J
    )
    assert r.status_code == 201
    assert r.json()["title"] == "😀"


def test_ac25_script_stored_and_returned_verbatim(env):
    content = f"{SCRIPT}&amp;<b>x</b>\"'"
    p = env.post(title=SCRIPT, content=content)
    assert p["title"] == SCRIPT and p["content"] == content
    d = env.anon.get(f"/api/posts/{p['id']}")
    assert d.json()["title"] == SCRIPT and d.json()["content"] == content
    assert d.headers["content-type"].startswith("application/json")
    assert env.anon.get("/api/posts").json()["items"][0]["title"] == SCRIPT
    row = env.rows()[0]
    assert row[1] == SCRIPT and row[2] == content
