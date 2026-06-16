import hashlib
import shutil
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class StoredObject(BaseModel):
    object_key: str
    public_url: str | None
    size_bytes: int
    sha256: str


class StorageProvider(Protocol):
    async def save(self, source: Path, object_key: str) -> StoredObject:
        """Persist an object and return storage metadata."""


class LocalStorageProvider:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def save(self, source: Path, object_key: str) -> StoredObject:
        target = self.root / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

        return StoredObject(
            object_key=object_key,
            public_url=_public_url_for(object_key),
            size_bytes=target.stat().st_size,
            sha256=_sha256_file(target),
        )


def _public_url_for(object_key: str) -> str | None:
    public_prefix = "public/"
    if not object_key.startswith(public_prefix):
        return None
    return f"/uploads/{object_key.removeprefix(public_prefix)}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
