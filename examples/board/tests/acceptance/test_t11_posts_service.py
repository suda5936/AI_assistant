"""T-11 (조회): AC-11~AC-14, AC-16. 서비스 함수 직접 호출.

parse_page의 앞자리 0 규칙은 T-12에서 구현하므로 제외한다.
"""

from datetime import timedelta

import pytest
from board.errors import PostNotFoundError
from board.services import posts as ps
from conftest import T0


def _make(db, user, n):
    return [ps.create_post(db, user, f"t{i}", f"c{i}", T0 + timedelta(minutes=i)) for i in range(n)]


# ---------- AC-11 ----------
def test_ac11_empty_list(db):
    page = ps.list_posts(db, 1)
    assert (page.items, page.total, page.page, page.size) == ([], 0, 1, 10)


# ---------- AC-12 ----------
def test_ac12_newest_first_and_ten_per_page(db, alice):
    posts = _make(db, alice, 12)
    page = ps.list_posts(db, 1)
    assert page.size == 10 and page.total == 12 and len(page.items) == 10
    assert [p.title for p in page.items] == [f"t{i}" for i in range(11, 1, -1)]
    assert page.items[0].author.username == "alice"
    assert posts[-1].id == page.items[0].id


def test_ac12_same_timestamp_ties_broken_by_id_desc(db, alice):
    made = [ps.create_post(db, alice, f"s{i}", "c", T0) for i in range(3)]
    ids = [p.id for p in ps.list_posts(db, 1).items]
    assert ids == sorted((p.id for p in made), reverse=True)


def test_ac12_created_order_not_insertion_order(db, alice):
    ps.create_post(db, alice, "newer", "c", T0 + timedelta(days=1))
    ps.create_post(db, alice, "older", "c", T0)
    assert [p.title for p in ps.list_posts(db, 1).items] == ["newer", "older"]


# ---------- AC-13 ----------
def test_ac13_eleven_posts_split_10_and_1(db, alice):
    _make(db, alice, 11)
    assert len(ps.list_posts(db, 1).items) == 10
    p2 = ps.list_posts(db, 2)
    assert len(p2.items) == 1 and p2.items[0].title == "t0" and p2.page == 2


def test_ac13_exactly_ten_is_single_page(db, alice):
    _make(db, alice, 10)
    p = ps.list_posts(db, 2)
    assert p.total == 10 and p.page == 1 and len(p.items) == 10


def test_ac13_twenty_one_has_three_pages(db, alice):
    _make(db, alice, 21)
    assert [len(ps.list_posts(db, n).items) for n in (1, 2, 3)] == [10, 10, 1]
    assert ps.list_posts(db, 4).page == 3


# ---------- AC-14 ----------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 1),
        ("", 1),
        ("abc", 1),
        ("1.5", 1),
        (" 2", 1),
        ("2 ", 1),
        ("+2", 1),
        ("１２", 1),
        ("1e3", 1),
        ("0", 1),
        ("-1", 1),
        ("-999", 1),
        ("1", 1),
        ("3", 3),
        ("999", 999),
        ("1000000000", 10**9),
        ("99999999999999999999", 10**9),
        ("-99999999999999999999", 1),
    ],
)
def test_ac14_parse_page(raw, expected):
    assert ps.parse_page(raw) == expected


def test_ac14_parse_page_huge_input_does_not_raise():
    assert ps.parse_page("9" * 10000) == 10**9
    assert ps.parse_page("-" + "9" * 10000) == 1


def test_ac14_out_of_range_pages_are_corrected(db, alice):
    _make(db, alice, 11)
    assert ps.list_posts(db, 0).page == 1
    assert ps.list_posts(db, -5).page == 1
    assert ps.list_posts(db, 999).page == 2
    assert ps.list_posts(db, 10**9).page == 2
    assert ps.list_posts(db, 10**9).items[0].title == "t0"


def test_ac14_empty_list_any_page_is_page1(db):
    p = ps.list_posts(db, 5)
    assert p.page == 1 and p.items == [] and p.total == 0


# ---------- AC-16 ----------
@pytest.mark.parametrize(
    "raw",
    ["0", "-1", "abc", "", "01", "1.0", " 1", "1 ", "+1", "9223372036854775808", "9" * 40, "１"],
)
def test_ac16_parse_post_id_invalid_is_not_found(raw):
    with pytest.raises(PostNotFoundError):
        ps.parse_post_id(raw)


def test_ac16_parse_post_id_valid_and_max():
    assert ps.parse_post_id("1") == 1
    assert ps.parse_post_id("42") == 42
    assert ps.parse_post_id("9223372036854775807") == 2**63 - 1


def test_ac16_get_missing_post(db, alice):
    with pytest.raises(PostNotFoundError):
        ps.get_post(db, 1)
    p = ps.create_post(db, alice, "t", "c", T0)
    assert ps.get_post(db, p.id).title == "t"
    with pytest.raises(PostNotFoundError):
        ps.get_post(db, p.id + 1)


def test_ac16_get_max_id_no_overflow(db):
    with pytest.raises(PostNotFoundError):
        ps.get_post(db, ps.parse_post_id("9223372036854775807"))


def test_ac16_deleted_post_not_found(db, alice):
    p = ps.create_post(db, alice, "t", "c", T0)
    ps.delete_post(db, p.id, alice)
    with pytest.raises(PostNotFoundError):
        ps.get_post(db, p.id)
