"""게시글 라우터. 요청 검증 → 서비스 호출 → 응답 변환만 한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from board.api.deps import get_current_user, get_db
from board.models import User
from board.schemas.error import ErrorResponse
from board.schemas.post import PostOut, PostPageOut, PostWriteRequest
from board.services import posts as post_service
from board.timeutil import utc_now

router = APIRouter(prefix="/api/posts")

_ERROR = {"model": ErrorResponse}
# FastAPI가 기본으로 붙이는 422(HTTPValidationError)를 실제 오류 형식으로 덮어쓴다.
_ERRORS_LIST = {422: _ERROR}
_ERRORS_DETAIL = {404: _ERROR, 422: _ERROR}
_ERRORS_CREATE = {401: _ERROR, 415: _ERROR, 422: _ERROR}
_ERRORS_UPDATE = {401: _ERROR, 403: _ERROR, 404: _ERROR, 415: _ERROR, 422: _ERROR}
# DELETE는 422가 나오지 않지만 FastAPI가 자동으로 넣으므로 형식만 실제 오류에 맞춘다.
_ERRORS_DELETE = {401: _ERROR, 403: _ERROR, 404: _ERROR, 415: _ERROR, 422: _ERROR}


@router.get("", response_model=PostPageOut, responses=_ERRORS_LIST)
def list_posts_endpoint(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[str | None, Query()] = None,
) -> PostPageOut:
    """글 목록. page는 원문을 받아 서비스가 보정한다."""
    result = post_service.list_posts(db, post_service.parse_page(page))
    return PostPageOut.from_page(result)


@router.post("", status_code=201, response_model=PostOut, responses=_ERRORS_CREATE)
def create_post_endpoint(
    body: PostWriteRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PostOut:
    """글 작성."""
    post = post_service.create_post(db, user, body.title, body.content, utc_now())
    return PostOut.from_model(post)


@router.get("/{post_id}", response_model=PostOut, responses=_ERRORS_DETAIL)
def get_post_endpoint(post_id: str, db: Annotated[Session, Depends(get_db)]) -> PostOut:
    """글 상세."""
    post = post_service.get_post(db, post_service.parse_post_id(post_id))
    return PostOut.from_model(post)


@router.put("/{post_id}", response_model=PostOut, responses=_ERRORS_UPDATE)
def update_post_endpoint(
    post_id: str,
    body: PostWriteRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PostOut:
    """글 수정. 작성자 본인만 가능."""
    post = post_service.update_post(
        db, post_service.parse_post_id(post_id), user, body.title, body.content
    )
    return PostOut.from_model(post)


@router.delete("/{post_id}", status_code=204, responses=_ERRORS_DELETE)
def delete_post_endpoint(
    post_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """글 삭제. 작성자 본인만 가능."""
    post_service.delete_post(db, post_service.parse_post_id(post_id), user)
