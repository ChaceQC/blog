# Blog Backend

FastAPI backend for the personal blog CMS.

## Local Development

The development workstation is Windows 11. Use UTF-8 for terminal output and
file operations.

```powershell
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
```

## Deployment Target

Production deployment targets Linux Debian with Docker Compose, Nginx, MySQL
and private container networks. Only Nginx should expose public `80/443`.
