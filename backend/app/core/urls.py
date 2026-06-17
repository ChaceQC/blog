from urllib.parse import urlencode


def public_file_download_url(*, file_id: int, token: str) -> str:
    return f"/api/public/files/{file_id}/download?{urlencode({'token': token})}"
