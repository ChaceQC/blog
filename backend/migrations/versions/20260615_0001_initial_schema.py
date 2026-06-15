"""创建初始数据库结构

Revision ID: 20260615_0001
Revises:
Create Date: 2026-06-15 15:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "20260615_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def long_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def pk_column() -> sa.Column:
    return sa.Column("id", bigint_unsigned(), autoincrement=True, nullable=False)


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        datetime_6(),
        server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        datetime_6(),
        server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )


def deleted_at_column() -> sa.Column:
    return sa.Column("deleted_at", datetime_6(), nullable=True)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        pk_column(),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column("avatar_file_id", bigint_unsigned(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False),
        sa.Column("last_login_at", datetime_6(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )

    op.create_table(
        "roles",
        pk_column(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
    )

    op.create_table(
        "permissions",
        pk_column(),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("group_name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )

    op.create_table(
        "categories",
        pk_column(),
        sa.Column("parent_id", bigint_unsigned(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name=op.f("fk_categories_parent_id_categories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )

    op.create_table(
        "tags",
        pk_column(),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("slug", name=op.f("uq_tags_slug")),
    )

    op.create_table(
        "friend_link_groups",
        pk_column(),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_friend_link_groups")),
        sa.UniqueConstraint("slug", name=op.f("uq_friend_link_groups_slug")),
    )

    op.create_table(
        "site_nav_groups",
        pk_column(),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_nav_groups")),
        sa.UniqueConstraint("slug", name=op.f("uq_site_nav_groups_slug")),
    )

    op.create_table(
        "files",
        pk_column(),
        sa.Column("storage", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("public_url", sa.String(length=1000), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", bigint_unsigned(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("uploader_id", bigint_unsigned(), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        created_at_column(),
        updated_at_column(),
        deleted_at_column(),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["users.id"],
            name=op.f("fk_files_uploader_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.UniqueConstraint("sha256", name=op.f("uq_files_sha256")),
    )
    op.create_index("idx_files_mime", "files", ["mime_type"], unique=False)
    op.create_index("idx_files_uploader", "files", ["uploader_id"], unique=False)

    op.create_foreign_key(
        op.f("fk_users_avatar_file_id_files"),
        "users",
        "files",
        ["avatar_file_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", bigint_unsigned(), nullable=False),
        sa.Column("role_id", bigint_unsigned(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", bigint_unsigned(), nullable=False),
        sa.Column("permission_id", bigint_unsigned(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
            name=op.f("pk_role_permissions"),
        ),
    )

    op.create_table(
        "refresh_tokens",
        pk_column(),
        sa.Column("user_id", bigint_unsigned(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", datetime_6(), nullable=False),
        sa.Column("revoked_at", datetime_6(), nullable=True),
        created_at_column(),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )

    op.create_table(
        "posts",
        pk_column(),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("content_md", long_text(), nullable=False),
        sa.Column("content_html", long_text(), nullable=False),
        sa.Column("cover_file_id", bigint_unsigned(), nullable=True),
        sa.Column("author_id", bigint_unsigned(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("allow_comment", sa.Boolean(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("view_count", bigint_unsigned(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.String(length=500), nullable=True),
        sa.Column("published_at", datetime_6(), nullable=True),
        created_at_column(),
        updated_at_column(),
        deleted_at_column(),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_posts_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cover_file_id"],
            ["files.id"],
            name=op.f("fk_posts_cover_file_id_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_posts")),
        sa.UniqueConstraint("slug", name=op.f("uq_posts_slug")),
    )
    op.create_index("idx_posts_author", "posts", ["author_id"], unique=False)
    op.create_index(
        "idx_posts_status_published",
        "posts",
        ["status", "published_at"],
        unique=False,
    )

    op.create_table(
        "pages",
        pk_column(),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("content_md", long_text(), nullable=False),
        sa.Column("content_html", long_text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("show_in_nav", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.String(length=500), nullable=True),
        created_at_column(),
        updated_at_column(),
        deleted_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
        sa.UniqueConstraint("slug", name=op.f("uq_pages_slug")),
    )

    op.create_table(
        "post_revisions",
        pk_column(),
        sa.Column("post_id", bigint_unsigned(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_md", long_text(), nullable=False),
        sa.Column("editor_id", bigint_unsigned(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["editor_id"],
            ["users.id"],
            name=op.f("fk_post_revisions_editor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_revisions_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post_revisions")),
    )

    op.create_table(
        "post_categories",
        sa.Column("post_id", bigint_unsigned(), nullable=False),
        sa.Column("category_id", bigint_unsigned(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_post_categories_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_categories_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "post_id",
            "category_id",
            name=op.f("pk_post_categories"),
        ),
    )

    op.create_table(
        "post_tags",
        sa.Column("post_id", bigint_unsigned(), nullable=False),
        sa.Column("tag_id", bigint_unsigned(), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_tags_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name=op.f("fk_post_tags_tag_id_tags"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("post_id", "tag_id", name=op.f("pk_post_tags")),
    )

    op.create_table(
        "file_usages",
        pk_column(),
        sa.Column("file_id", bigint_unsigned(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", bigint_unsigned(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name=op.f("fk_file_usages_file_id_files"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_usages")),
    )

    op.create_table(
        "friend_links",
        pk_column(),
        sa.Column("group_id", bigint_unsigned(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("avatar_file_id", bigint_unsigned(), nullable=True),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("rss_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", datetime_6(), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["avatar_file_id"],
            ["files.id"],
            name=op.f("fk_friend_links_avatar_file_id_files"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["friend_link_groups.id"],
            name=op.f("fk_friend_links_group_id_friend_link_groups"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_friend_links")),
    )

    op.create_table(
        "site_nav_items",
        pk_column(),
        sa.Column("group_id", bigint_unsigned(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("icon_file_id", bigint_unsigned(), nullable=True),
        sa.Column("icon_url", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("open_target", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("click_count", bigint_unsigned(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["site_nav_groups.id"],
            name=op.f("fk_site_nav_items_group_id_site_nav_groups"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["icon_file_id"],
            ["files.id"],
            name=op.f("fk_site_nav_items_icon_file_id_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_nav_items")),
    )

    op.create_table(
        "settings",
        pk_column(),
        sa.Column("key_name", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("group_name", sa.String(length=64), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("updated_by", bigint_unsigned(), nullable=True),
        sa.Column("updated_at", datetime_6(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
        sa.UniqueConstraint("key_name", name=op.f("uq_settings_key_name")),
    )

    op.create_table(
        "audit_logs",
        pk_column(),
        sa.Column("actor_id", bigint_unsigned(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", bigint_unsigned(), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )

    op.create_table(
        "login_logs",
        pk_column(),
        sa.Column("user_id", bigint_unsigned(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_login_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_logs")),
    )

    op.create_table(
        "security_events",
        pk_column(),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("actor_id", bigint_unsigned(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_security_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("security_events")
    op.drop_table("login_logs")
    op.drop_table("audit_logs")
    op.drop_table("settings")
    op.drop_table("site_nav_items")
    op.drop_table("friend_links")
    op.drop_table("file_usages")
    op.drop_table("post_tags")
    op.drop_table("post_categories")
    op.drop_table("post_revisions")
    op.drop_table("pages")
    op.drop_table("posts")
    op.drop_table("refresh_tokens")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_constraint(
        op.f("fk_users_avatar_file_id_files"),
        "users",
        type_="foreignkey",
    )
    op.drop_table("files")
    op.drop_table("site_nav_groups")
    op.drop_table("friend_link_groups")
    op.drop_table("tags")
    op.drop_table("categories")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
