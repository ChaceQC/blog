FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Shanghai \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple \
    UV_HTTP_TIMEOUT=300 \
    UV_CONCURRENT_DOWNLOADS=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN rm -f /etc/apt/sources.list \
    && printf '%s\n' \
      'Types: deb' \
      'URIs: https://mirrors.cloud.tencent.com/debian' \
      'Suites: trixie trixie-updates' \
      'Components: main contrib non-free non-free-firmware' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      '' \
      'Types: deb' \
      'URIs: https://mirrors.cloud.tencent.com/debian-security' \
      'Suites: trixie-security' \
      'Components: main contrib non-free non-free-firmware' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      > /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.11.7 \
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
