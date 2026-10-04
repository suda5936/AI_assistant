"""posts 테이블 생성.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """posts 테이블과 인덱스 2개를 만든다."""
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_posts_created_at_id", "posts", ["created_at", "id"])
    op.create_index("ix_posts_author_id", "posts", ["author_id"])


def downgrade() -> None:
    """인덱스, 테이블 순으로 삭제한다."""
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_index("ix_posts_created_at_id", table_name="posts")
    op.drop_table("posts")
