"""T-11 (수정·삭제·권한): AC-21, AC-22, AC-24(서비스 계층). 서비스 함수 직접 호출."""

from datetime import timedelta

import pytest
from board.errors import ForbiddenError, PostNotFoundError, ValidationFailedError
from board.services import posts as ps
from conftest import T0


def _fields(exc_info):
    return [(d.field, d.message) for d in exc_info.value.details]


# ---------- AC-21 ----------
def test_ac21_update_changes_title_content_only(db, alice, snapshot):
    p = ps.create_post(db, alice, "old", "oldc", T0)
    before = snapshot()[0]
    out = ps.update_post(db, p.id, alice, "new", "newc")
    assert (out.title, out.content) == ("new", "newc")
    after = snapshot()[0]
    assert after[1:3] == ("new", "newc")
    assert (after[0], after[3], after[4]) == (before[0], before[3], before[4])
    assert ps.list_posts(db, 1).items[0].title == "new"
    assert ps.get_post(db, p.id).content == "newc"


def test_ac21_update_same_values_and_repeat(db, alice):
    p = ps.create_post(db, alice, "t", "c", T0)
    ps.update_post(db, p.id, alice, "t", "c")
    ps.update_post(db, p.id, alice, "t2", "c2")
    ps.update_post(db, p.id, alice, "t2", "c2")
    assert ps.get_post(db, p.id).title == "t2"


def test_ac21_update_keeps_list_order(db, alice):
    made = [ps.create_post(db, alice, f"t{i}", "c", T0 + timedelta(minutes=i)) for i in range(3)]
    ps.update_post(db, made[0].id, alice, "edited", "c")
    assert [p.title for p in ps.list_posts(db, 1).items] == ["t2", "t1", "edited"]


@pytest.mark.parametrize(
    ("title", "content", "expected"),
    [
        ("", "c", [("title", "제목을 입력해 주세요.")]),
        ("  ", "c", [("title", "제목을 입력해 주세요.")]),
        ("t", "\n\t", [("content", "내용을 입력해 주세요.")]),
        ("a" * 101, "c", [("title", "제목은 100자 이하여야 합니다.")]),
        ("t", "a" * 5001, [("content", "내용은 5000자 이하여야 합니다.")]),
        ("a\ud800", "c", [("title", "제목에 사용할 수 없는 문자가 포함되어 있습니다.")]),
    ],
)
def test_ac21_update_invalid_leaves_db_unchanged(db, alice, snapshot, title, content, expected):
    p = ps.create_post(db, alice, "keep", "keepc", T0)
    before = snapshot()
    with pytest.raises(ValidationFailedError) as e:
        ps.update_post(db, p.id, alice, title, content)
    assert _fields(e) == expected
    assert snapshot() == before


def test_ac21_update_boundaries_ok(db, alice):
    p = ps.create_post(db, alice, "t", "c", T0)
    out = ps.update_post(db, p.id, alice, "a" * 100, "b" * 5000)
    assert len(out.title) == 100 and len(out.content) == 5000


def test_ac21_update_missing_post(db, alice):
    with pytest.raises(PostNotFoundError):
        ps.update_post(db, 12345, alice, "t", "c")
    with pytest.raises(PostNotFoundError):
        ps.update_post(db, ps.parse_post_id("9223372036854775807"), alice, "t", "c")


# ---------- AC-22 ----------
def test_ac22_delete_removes_from_list_and_get(db, alice, snapshot):
    a = ps.create_post(db, alice, "a", "c", T0)
    b = ps.create_post(db, alice, "b", "c", T0 + timedelta(minutes=1))
    ps.delete_post(db, b.id, alice)
    assert [p.id for p in ps.list_posts(db, 1).items] == [a.id]
    assert ps.list_posts(db, 1).total == 1
    assert [r[0] for r in snapshot()] == [a.id]
    with pytest.raises(PostNotFoundError):
        ps.get_post(db, b.id)


def test_ac22_delete_twice_second_is_not_found(db, alice):
    p = ps.create_post(db, alice, "t", "c", T0)
    ps.delete_post(db, p.id, alice)
    with pytest.raises(PostNotFoundError):
        ps.delete_post(db, p.id, alice)


def test_ac22_delete_missing(db, alice):
    with pytest.raises(PostNotFoundError):
        ps.delete_post(db, 999, alice)


def test_ac22_delete_page_shrinks(db, alice):
    made = [ps.create_post(db, alice, f"t{i}", "c", T0 + timedelta(minutes=i)) for i in range(11)]
    ps.delete_post(db, made[-1].id, alice)
    p = ps.list_posts(db, 2)
    assert p.page == 1 and p.total == 10 and len(p.items) == 10


# ---------- AC-24 (서비스 계층) ----------
def test_ac24_ensure_author(db, alice, bob):
    p = ps.create_post(db, alice, "t", "c", T0)
    ps.ensure_author(p, alice)
    with pytest.raises(ForbiddenError):
        ps.ensure_author(p, bob)


def test_ac24_update_other_users_post_forbidden_db_unchanged(db, alice, bob, snapshot):
    p = ps.create_post(db, alice, "mine", "minec", T0)
    before = snapshot()
    with pytest.raises(ForbiddenError):
        ps.update_post(db, p.id, bob, "hacked", "hackedc")
    assert snapshot() == before
    got = ps.get_post(db, p.id)
    assert (got.title, got.content, got.author_id) == ("mine", "minec", alice.id)


def test_ac24_delete_other_users_post_forbidden_db_unchanged(db, alice, bob, snapshot):
    p = ps.create_post(db, alice, "mine", "minec", T0)
    before = snapshot()
    with pytest.raises(ForbiddenError):
        ps.delete_post(db, p.id, bob)
    assert snapshot() == before
    assert ps.get_post(db, p.id).title == "mine"


def test_ac24_forbidden_takes_precedence_over_validation(db, alice, bob, snapshot):
    p = ps.create_post(db, alice, "mine", "minec", T0)
    before = snapshot()
    with pytest.raises(ForbiddenError):
        ps.update_post(db, p.id, bob, "", "")
    with pytest.raises(ForbiddenError):
        ps.update_post(db, p.id, bob, "a\ud800", "x" * 5001)
    assert snapshot() == before


def test_ac24_not_found_takes_precedence_over_forbidden_and_validation(db, bob):
    with pytest.raises(PostNotFoundError):
        ps.update_post(db, 777, bob, "", "")
    with pytest.raises(PostNotFoundError):
        ps.delete_post(db, 777, bob)


def test_ac24_owner_can_still_edit_after_failed_attempt(db, alice, bob):
    p = ps.create_post(db, alice, "mine", "c", T0)
    with pytest.raises(ForbiddenError):
        ps.delete_post(db, p.id, bob)
    ps.update_post(db, p.id, alice, "mine2", "c2")
    assert ps.get_post(db, p.id).title == "mine2"
