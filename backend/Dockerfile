FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_HTTP_TIMEOUT=300 \
    UV_CONCURRENT_DOWNLOADS=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.7 \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY main.py ./

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["python", "-m", "app.server"]
