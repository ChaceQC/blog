from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class StoredObject(BaseModel):
    object_key: str
    public_url: str | None
    size_bytes: int
    sha256: str


class StorageProvider(Protocol):
    async def save_public(self, source: Path, object_key: str) -> StoredObject:
        """Persist a public object and return storage metadata."""
