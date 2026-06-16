from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import BlogFile, FileUsage


class FileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[BlogFile, int]]:
        result = await self.session.execute(
            select(BlogFile, func.count(FileUsage.id))
            .outerjoin(FileUsage, FileUsage.file_id == BlogFile.id)
            .where(BlogFile.deleted_at.is_(None))
            .group_by(BlogFile.id)
            .order_by(BlogFile.updated_at.desc(), BlogFile.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return [(file, int(usage_count)) for file, usage_count in result.all()]

    async def list_public_listed_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[BlogFile]:
        result = await self.session.execute(
            select(BlogFile)
            .where(
                BlogFile.deleted_at.is_(None),
                BlogFile.visibility == "public",
                BlogFile.public_listed.is_(True),
                BlogFile.status == "active",
            )
            .order_by(BlogFile.updated_at.desc(), BlogFile.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def get_file(self, file_id: int) -> BlogFile | None:
        result = await self.session.execute(
            select(BlogFile).where(
                BlogFile.id == file_id,
                BlogFile.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    async def get_file_by_sha256(self, sha256: str) -> BlogFile | None:
        result = await self.session.execute(
            select(BlogFile).where(
                BlogFile.sha256 == sha256,
                BlogFile.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    async def list_storage_object_keys(self) -> Sequence[str]:
        result = await self.session.execute(
            select(BlogFile.object_key).where(
                BlogFile.status.in_(("active", "deleted")),
            ),
        )
        return result.scalars().all()

    async def list_deleted_files_for_cleanup(
        self,
        *,
        deleted_before: datetime,
        limit: int,
    ) -> Sequence[tuple[BlogFile, int]]:
        result = await self.session.execute(
            select(BlogFile, func.count(FileUsage.id))
            .outerjoin(FileUsage, FileUsage.file_id == BlogFile.id)
            .where(
                BlogFile.status == "deleted",
                BlogFile.deleted_at.is_not(None),
                BlogFile.deleted_at <= deleted_before,
            )
            .group_by(BlogFile.id)
            .order_by(BlogFile.deleted_at.asc(), BlogFile.id.asc())
            .limit(limit),
        )
        return [(file, int(usage_count)) for file, usage_count in result.all()]

    async def delete_file_record(self, file_id: int) -> None:
        await self.session.execute(delete(BlogFile).where(BlogFile.id == file_id))

    async def create_file(
        self,
        *,
        storage: str,
        bucket: str | None,
        object_key: str,
        public_url: str | None,
        original_name: str,
        mime_type: str,
        extension: str,
        size_bytes: int,
        sha256: str,
        width: int | None,
        height: int | None,
        alt_text: str | None,
        uploader_id: int | None,
        visibility: str,
        public_listed: bool,
    ) -> BlogFile:
        file = BlogFile(
            storage=storage,
            bucket=bucket,
            object_key=object_key,
            public_url=public_url,
            original_name=original_name,
            mime_type=mime_type,
            extension=extension,
            size_bytes=size_bytes,
            sha256=sha256,
            width=width,
            height=height,
            alt_text=alt_text,
            uploader_id=uploader_id,
            visibility=visibility,
            public_listed=public_listed,
            status="active",
        )
        self.session.add(file)
        await self.session.flush()
        return file

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)
