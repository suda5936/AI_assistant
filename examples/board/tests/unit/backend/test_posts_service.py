"""services/posts.py 단위 테스트."""

from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from board.errors import (
    FieldError,
    ForbiddenError,
    PostNotFoundError,
    ValidationFailedError,
)
from board.models import Post, User
from board.services import posts as post_service
from board.services.posts import PAGE_SIZE, parse_page, parse_post_id
from sqlalchemy import func, select
from sqlalchemy.orm import Session

NOW = datetime(2026, 1, 1, 12, 0, 0)
MakeUser = Callable[[str], User]


def _count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Post)) or 0


def _add_posts(db: Session, author: User, count: int) -> list[Post]:
    created = []
    for index in range(count):
        when = NOW + timedelta(minutes=index)
        created.append(post_service.create_post(db, author, f"t{index}", "c", when))
    return created


@pytest.mark.parametrize(
    "raw", [None, "", "abc", "1.5", " 2", "+2", "1e3", "２", "0", "-1", "-0", "-999999999"]
)
def test_parse_page_falls_back_to_one(raw: str | None) -> None:
    assert parse_page(raw) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3", 3), ("1", 1), ("999999999", 999999999), ("0003", 3), ("1000000000", 10**9)],
)
def test_parse_page_numbers(raw: str, expected: int) -> None:
    assert parse_page(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0000000005", 5),
        ("0" * 20 + "5", 5),
        ("0999999999", 999999999),
        ("0" * 5000 + "7", 7),
        ("0" + "1" * 9, 111111111),
        ("0" + "1" + "0" * 9, 10**9),
    ],
)
def test_parse_page_leading_zeros_use_value(raw: str, expected: int) -> None:
    assert parse_page(raw) == expected


@pytest.mark.parametrize(
    "raw", ["000", "-0", "-0000000005", "-" + "0" * 5000 + "7", "-" + "0" * 5000]
)
def test_parse_page_leading_zeros_low_values(raw: str) -> None:
    assert parse_page(raw) == 1


def test_parse_page_huge_values() -> None:
    assert parse_page("9" * 30) == 10**9
    assert parse_page("-" + "9" * 30) == 1


@pytest.mark.parametrize(
    "raw", ["0", "-1", "abc", "01", "", " 1", "1.0", "９", "9223372036854775808", "9" * 40]
)
def test_parse_post_id_rejects(raw: str) -> None:
    with pytest.raises(PostNotFoundError):
        parse_post_id(raw)


def test_parse_post_id_accepts() -> None:
    assert parse_post_id("1") == 1
    assert parse_post_id("9223372036854775807") == 2**63 - 1


def test_list_posts_empty(db: Session) -> None:
    page = post_service.list_posts(db, 5)
    assert (page.items, page.total, page.page, page.size) == ([], 0, 1, PAGE_SIZE)


def test_list_posts_orders_newest_first_then_id(db: Session, make_user: MakeUser) -> None:
    author = make_user("alice")
    # id 순서와 시각 순서가 어긋나게 만든다: A는 id가 가장 작지만 가장 최신이다.
    newest = post_service.create_post(db, author, "a", "c", NOW + timedelta(hours=1))
    older_first = post_service.create_post(db, author, "b", "c", NOW)
    older_second = post_service.create_post(db, author, "c", "c", NOW)
    page = post_service.list_posts(db, 1)
    assert newest.id < older_first.id < older_second.id
    assert [post.id for post in page.items] == [newest.id, older_second.id, older_first.id]
    assert page.items[0].author.username == "alice"


def test_list_posts_pagination_boundaries(db: Session, make_user: MakeUser) -> None:
    _add_posts(db, make_user("alice"), 11)
    first = post_service.list_posts(db, 1)
    second = post_service.list_posts(db, 2)
    assert (len(first.items), first.total, first.page) == (10, 11, 1)
    assert (len(second.items), second.page) == (1, 2)
    assert second.items[0].title == "t0"


def test_list_posts_exactly_ten_is_single_page(db: Session, make_user: MakeUser) -> None:
    _add_posts(db, make_user("alice"), 10)
    page = post_service.list_posts(db, 2)
    assert (len(page.items), page.page, page.total) == (10, 1, 10)


def test_list_posts_clamps_page(db: Session, make_user: MakeUser) -> None:
    _add_posts(db, make_user("alice"), 11)
    assert post_service.list_posts(db, 99).page == 2
    assert post_service.list_posts(db, 10**9).page == 2
    assert post_service.list_posts(db, 0).page == 1
    assert post_service.list_posts(db, -3).page == 1


def test_get_post_found_and_missing(db: Session, make_user: MakeUser) -> None:
    created = post_service.create_post(db, make_user("alice"), "t", "c", NOW)
    assert post_service.get_post(db, created.id).author.username == "alice"
    with pytest.raises(PostNotFoundError):
        post_service.get_post(db, created.id + 1)
    with pytest.raises(PostNotFoundError):
        post_service.get_post(db, post_service.MAX_POST_ID)


def test_create_post_stores_author_and_time_unchanged(db: Session, make_user: MakeUser) -> None:
    author = make_user("alice")
    post = post_service.create_post(db, author, "  <b>제목</b> ", "줄1\n줄2 ", NOW)
    assert post.author_id == author.id
    assert post.created_at == NOW
    assert post.title == "  <b>제목</b> "
    assert post.content == "줄1\n줄2 "
    assert post.author.username == "alice"


def test_create_post_invalid_saves_nothing(db: Session, make_user: MakeUser) -> None:
    with pytest.raises(ValidationFailedError) as caught:
        post_service.create_post(db, make_user("alice"), " ", "", NOW)
    assert [d.field for d in caught.value.details] == ["title", "content"]
    assert _count(db) == 0


def test_update_post_changes_only_title_and_content(db: Session, make_user: MakeUser) -> None:
    author = make_user("alice")
    post = post_service.create_post(db, author, "old", "old", NOW)
    updated = post_service.update_post(db, post.id, author, "new", "new content")
    assert (updated.title, updated.content) == ("new", "new content")
    assert updated.created_at == NOW
    assert updated.author_id == author.id


def test_update_post_validation_failure_keeps_db(db: Session, make_user: MakeUser) -> None:
    author = make_user("alice")
    post = post_service.create_post(db, author, "old", "old", NOW)
    with pytest.raises(ValidationFailedError) as caught:
        post_service.update_post(db, post.id, author, "", "new")
    assert caught.value.details == [FieldError("title", "제목을 입력해 주세요.")]
    db.expire_all()
    stored = post_service.get_post(db, post.id)
    assert (stored.title, stored.content) == ("old", "old")


def test_update_post_by_other_user_is_forbidden_before_validation(
    db: Session, make_user: MakeUser
) -> None:
    author, other = make_user("alice"), make_user("bobby")
    post = post_service.create_post(db, author, "old", "old", NOW)
    with pytest.raises(ForbiddenError):
        post_service.update_post(db, post.id, other, "", "")
    db.expire_all()
    assert post_service.get_post(db, post.id).title == "old"


def test_update_missing_post(db: Session, make_user: MakeUser) -> None:
    with pytest.raises(PostNotFoundError):
        post_service.update_post(db, 1, make_user("alice"), "t", "c")


def test_delete_post_removes_it(db: Session, make_user: MakeUser) -> None:
    author = make_user("alice")
    post = post_service.create_post(db, author, "t", "c", NOW)
    post_id = post.id
    post_service.delete_post(db, post_id, author)
    with pytest.raises(PostNotFoundError):
        post_service.get_post(db, post_id)
    assert _count(db) == 0


def test_delete_post_by_other_user_is_forbidden(db: Session, make_user: MakeUser) -> None:
    author, other = make_user("alice"), make_user("bobby")
    post = post_service.create_post(db, author, "t", "c", NOW)
    with pytest.raises(ForbiddenError):
        post_service.delete_post(db, post.id, other)
    assert _count(db) == 1


def test_delete_missing_post(db: Session, make_user: MakeUser) -> None:
    with pytest.raises(PostNotFoundError):
        post_service.delete_post(db, 1, make_user("alice"))


def test_ensure_author(db: Session, make_user: MakeUser) -> None:
    author, other = make_user("alice"), make_user("bobby")
    post = post_service.create_post(db, author, "t", "c", NOW)
    post_service.ensure_author(post, author)
    with pytest.raises(ForbiddenError):
        post_service.ensure_author(post, other)
