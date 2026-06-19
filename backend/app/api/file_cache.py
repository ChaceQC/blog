from pathlib import Path

from app.core.auth import utc_now


def signed_file_cache_headers(*, path: Path, expires: int) -> dict[str, str]:
    stat = path.stat()
    max_age = max(0, expires - int(utc_now().timestamp()))
    return {
        "Cache-Control": f"private, max-age={max_age}, immutable",
        "ETag": f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"',
        "X-Content-Type-Options": "nosniff",
    }
