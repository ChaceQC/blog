from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    BIGINT_UNSIGNED,
    DATETIME_6,
    LONG_TEXT,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    pk_column,
)


class Post(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("idx_posts_status_published", "status", "published_at"),
        Index("idx_posts_author", "author_id"),
    )

    id: Mapped[int] = pk_column()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_md: Mapped[str] = mapped_column(LONG_TEXT, nullable=False)
    content_html: Mapped[str] = mapped_column(LONG_TEXT, nullable=False)
    cover_file_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )
    allow_comment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_count: Mapped[int] = mapped_column(BIGINT_UNSIGNED, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(BIGINT_UNSIGNED, default=0, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)


class PostRevision(Base):
    __tablename__ = "post_revisions"

    id: Mapped[int] = pk_column()
    post_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_md: Mapped[str] = mapped_column(LONG_TEXT, nullable=False)
    editor_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class PostLike(TimestampMixin, Base):
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "visitor_hash",
            name="uq_post_likes_post_visitor",
        ),
        Index("idx_post_likes_post_active", "post_id", "active"),
    )

    id: Mapped[int] = pk_column()
    post_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    visitor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = pk_column()
    parent_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = pk_column()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class PostCategory(Base):
    __tablename__ = "post_categories"

    post_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )


class PostTag(Base):
    __tablename__ = "post_tags"

    post_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Page(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "pages"

    id: Mapped[int] = pk_column()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    content_md: Mapped[str] = mapped_column(LONG_TEXT, nullable=False)
    content_html: Mapped[str] = mapped_column(LONG_TEXT, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    show_in_nav: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
