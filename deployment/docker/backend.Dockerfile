# Backend image. Build context: repository root.
#   docker build -f deployment/docker/backend.Dockerfile -t ecomind-backend .
FROM python:3.12-slim

ENV PYTHONPATH=/srv/backend:/srv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 ecomind \
    && mkdir -p /var/lib/ecomind/storage /var/lib/ecomind/artifacts \
    && chown -R ecomind /var/lib/ecomind

WORKDIR /srv/backend
COPY backend/pyproject.toml backend/README.md backend/requirements.lock ./
# Third-party dependencies come from the hash-verified lock file (the exact versions CI tested),
# in their own layer so application changes do not reinstall them.
RUN pip install --require-hashes -r requirements.lock
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
# The forecasting / anomaly algorithms are developed and benchmarked in the isolated ml/
# capability. Only the pure-numpy module is shipped (loaded by name at run time); nothing else
# from ml/ is needed in the image.
COPY ml/__init__.py /srv/ml/__init__.py
COPY ml/time_series/__init__.py /srv/ml/time_series/__init__.py
COPY ml/time_series/algorithms.py /srv/ml/time_series/algorithms.py
# Installs the application itself (dependencies are already pinned above); PYTHONPATH makes
# /srv/backend/app (which also holds alembic.ini and migrations next to it) the package that is
# imported, so mounted dev code wins in compose.
RUN pip install --no-deps .

USER ecomind
EXPOSE 8000
# Configuration comes entirely from environment variables (see backend/.env.example).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
