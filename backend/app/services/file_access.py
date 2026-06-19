from dataclasses import dataclass
from datetime import datetime

from app.models.file import BlogFile


@dataclass(frozen=True)
class TemporaryFileAccess:
    file: BlogFile
    token: str
    expires_at: datetime
