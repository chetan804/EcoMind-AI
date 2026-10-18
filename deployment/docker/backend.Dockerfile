# Backend image. Build context: repository root.
#   docker build -f deployment/docker/backend.Dockerfile -t ecomind-backend .
FROM python:3.12-slim

ENV PYTHONPATH=/srv/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 ecomind \
    && mkdir -p /var/lib/ecomind/storage /var/lib/ecomind/artifacts \
    && chown -R ecomind /var/lib/ecomind

WORKDIR /srv/backend
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
# Installs the dependencies; PYTHONPATH makes /srv/backend/app (which also holds alembic.ini and
# migrations next to it) the package that is imported, so mounted dev code wins in compose.
RUN pip install .

USER ecomind
EXPOSE 8000
# Configuration comes entirely from environment variables (see backend/.env.example).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
