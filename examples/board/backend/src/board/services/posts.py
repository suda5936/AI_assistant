"""게시글 조회·작성·수정·삭제와 소유권 검사."""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from board.errors import ForbiddenError, PostNotFoundError
from board.models import Post, User
from board.services.validation import validate_post

PAGE_SIZE: Final = 10
MAX_POST_ID: Final = 2**63 - 1
_MAX_PAGE_DIGITS: Final = 9
_HUGE_PAGE: Final = 10**9
_PAGE_PATTERN: Final = re.compile(r"-?[0-9]+", re.ASCII)
_POST_ID_PATTERN: Final = re.compile(r"[1-9][0-9]{0,18}", re.ASCII)


@dataclass(frozen=True)
class PostPage:
    """목록 한 페이지."""

    items: list[Post]
    total: int
    page: int
    size: int


def parse_page(raw: str | None) -> int:
    """?page= 원문을 요청 페이지 번호로 바꾼다. 예외를 던지지 않는다."""
    if raw is None or _PAGE_PATTERN.fullmatch(raw) is None:
        return 1
    negative = raw.startswith("-")
    significant = raw.lstrip("-").lstrip("0")
    if len(significant) > _MAX_PAGE_DIGITS:
        return 1 if negative else _HUGE_PAGE
    if negative:
        return 1
    return max(int(significant or "0"), 1)


def parse_post_id(raw: str) -> int:
    """경로의 글 ID 원문을 정수로 바꾼다.

    Raises:
        PostNotFoundError: 양의 정수 형식이 아니거나 범위를 넘을 때
    """
    if _POST_ID_PATTERN.fullmatch(raw) is None or int(raw) > MAX_POST_ID:
        raise PostNotFoundError
    return int(raw)


def list_posts(db: Session, requested_page: int) -> PostPage:
    """최신순 목록의 한 페이지를 돌려준다. 범위 밖 페이지는 보정한다."""
    total = db.scalar(select(func.count()).select_from(Post)) or 0
    last_page = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(requested_page, 1), last_page)
    statement = (
        select(Post)
        .options(joinedload(Post.author))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    items = list(db.scalars(statement))
    return PostPage(items=items, total=total, page=page, size=PAGE_SIZE)


def get_post(db: Session, post_id: int) -> Post:
    """글 하나를 돌려준다.

    Raises:
        PostNotFoundError: 해당 id의 글이 없을 때
    """
    post = db.scalar(select(Post).options(joinedload(Post.author)).where(Post.id == post_id))
    if post is None:
        raise PostNotFoundError
    return post


def create_post(db: Session, author: User, title: str, content: str, now: datetime) -> Post:
    """검증 후 글을 저장해 돌려준다.

    Raises:
        ValidationFailedError: 제목·내용이 규칙에 맞지 않을 때
    """
    validate_post(title, content)
    post = Post(title=title, content=content, author_id=author.id, created_at=now)
    db.add(post)
    db.commit()
    return get_post(db, post.id)


def ensure_author(post: Post, user: User) -> None:
    """글쓴이 본인인지 확인한다.

    Raises:
        ForbiddenError: post.author_id != user.id
    """
    if post.author_id != user.id:
        raise ForbiddenError


def update_post(db: Session, post_id: int, user: User, title: str, content: str) -> Post:
    """본인 글의 제목·내용을 바꾼다. 검증 실패·권한 없음이면 DB는 변하지 않는다.

    Raises:
        PostNotFoundError, ForbiddenError, ValidationFailedError
    """
    post = get_post(db, post_id)
    ensure_author(post, user)
    validate_post(title, content)
    post.title = title
    post.content = content
    db.commit()
    return get_post(db, post_id)


def delete_post(db: Session, post_id: int, user: User) -> None:
    """본인 글을 물리 삭제한다.

    Raises:
        PostNotFoundError, ForbiddenError
    """
    post = get_post(db, post_id)
    ensure_author(post, user)
    db.delete(post)
    db.commit()
