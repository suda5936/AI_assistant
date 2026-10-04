"""posts 테이블 모델."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from board.db import Base
from board.models.user import User


class Post(Base):
    """게시글. 제목·내용은 입력 그대로 저장하고, 삭제하면 물리 삭제한다."""

    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_created_at_id", "created_at", "id"),
        Index("ix_posts_author_id", "author_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    author: Mapped[User] = relationship()
