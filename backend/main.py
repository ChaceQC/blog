from app.core.config import get_settings
from app.main import app


def main() -> None:
    """本地开发入口，用于 `uv run python main.py`。"""
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.dev_server_host, port=settings.dev_server_port)


if __name__ == "__main__":
    main()
