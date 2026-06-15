from datetime import datetime

from sqlalchemy import BigInteger, DateTime, MetaData, Text, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column

MYSQL_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

BIGINT_UNSIGNED = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
DATETIME_6 = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT = Text().with_variant(mysql.LONGTEXT(), "mysql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=MYSQL_NAMING_CONVENTION)


def pk_column() -> MappedColumn[int]:
    return mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)
