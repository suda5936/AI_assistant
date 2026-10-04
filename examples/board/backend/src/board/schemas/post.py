"""게시글 요청·응답 스키마."""

from pydantic import BaseModel

from board.models import Post
from board.services.posts import PostPage
from board.timeutil import to_iso_utc


class PostWriteRequest(BaseModel):
    """글 작성·수정 요청. 길이 검증은 서비스가 맡는다."""

    title: str
    content: str


class AuthorOut(BaseModel):
    """작성자 공개 정보. 비밀번호 관련 필드를 두지 않는다."""

    id: int
    username: str


class PostSummaryOut(BaseModel):
    """목록 항목 응답."""

    id: int
    title: str
    author: AuthorOut
    created_at: str

    @classmethod
    def from_model(cls, post: Post) -> "PostSummaryOut":
        """모델에서 응답을 만든다."""
        return cls(
            id=post.id,
            title=post.title,
            author=AuthorOut(id=post.author.id, username=post.author.username),
            created_at=to_iso_utc(post.created_at),
        )


class PostOut(BaseModel):
    """글 상세 응답."""

    id: int
    title: str
    content: str
    author: AuthorOut
    created_at: str

    @classmethod
    def from_model(cls, post: Post) -> "PostOut":
        """모델에서 응답을 만든다."""
        return cls(
            id=post.id,
            title=post.title,
            content=post.content,
            author=AuthorOut(id=post.author.id, username=post.author.username),
            created_at=to_iso_utc(post.created_at),
        )


class PostPageOut(BaseModel):
    """목록 페이지 응답."""

    items: list[PostSummaryOut]
    total: int
    page: int
    size: int

    @classmethod
    def from_page(cls, page: PostPage) -> "PostPageOut":
        """서비스 결과에서 응답을 만든다."""
        return cls(
            items=[PostSummaryOut.from_model(post) for post in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )
