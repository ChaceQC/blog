from app.main import app


def main() -> None:
    """Development entry point used by `uv run python main.py`."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
