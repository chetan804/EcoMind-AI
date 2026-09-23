#!/bin/sh
# EcoMind-AI backend container entrypoint.
# Runs Alembic migrations to head, then execs the server command.
set -e

echo "[entrypoint] running Alembic migrations to head…"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
