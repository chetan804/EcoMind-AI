# EcoMind-AI backend image.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

# System deps: libpq (asyncpg), curl for healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first (cacheable layer), then application code.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN chmod +x scripts/docker-entrypoint.sh

# Non-root runtime user; uploads land under /srv/app/data (mount a volume).
RUN useradd --system --create-home --uid 10001 ecomind \
    && mkdir -p /srv/app/data/uploads \
    && chown -R ecomind:ecomind /srv/app
USER ecomind

ENV ECOMIND_DATA_DIR=/srv/app/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
