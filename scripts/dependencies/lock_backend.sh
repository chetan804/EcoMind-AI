#!/usr/bin/env bash
# Regenerate the hash-pinned Python lock files: backend (from backend/pyproject.toml) and the ML
# capability (from ml/requirements-dev.txt).
#
#   scripts/dependencies/lock_backend.sh          rewrite backend/requirements.lock,
#                                                 backend/requirements-dev.lock and
#                                                 ml/requirements-dev.lock
#   scripts/dependencies/lock_backend.sh --check  fail if the committed files are out of date
#
# Needs uv (pip install uv). All files are universal (Python 3.11 and 3.12, all platforms).
# Upgrade deliberately: add --upgrade (or --upgrade-package NAME) to the uv commands below, then
# run the full backend test suite before committing.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root/backend"

check=false
[[ "${1:-}" == "--check" ]] && check=true

compile() {
  local out="$1"
  shift
  uv pip compile pyproject.toml "$@" \
    --universal --python-version 3.11 --generate-hashes --no-header --quiet \
    --constraint lock-constraints.txt --output-file "$out"
}

compile_ml() {
  (cd ../ml && uv pip compile requirements-dev.txt \
    --universal --python-version 3.11 --generate-hashes --no-header --quiet \
    --constraint ../backend/lock-constraints.txt --output-file "$1")
}

if $check; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  # Re-resolving without --upgrade keeps the versions already in the committed files, so the check
  # only fails when pyproject.toml and the lock files disagree.
  cp requirements.lock "$tmp/requirements.lock"
  cp requirements-dev.lock "$tmp/requirements-dev.lock"
  compile "$tmp/requirements.lock"
  compile "$tmp/requirements-dev.lock" --extra dev
  diff -u requirements.lock "$tmp/requirements.lock"
  diff -u requirements-dev.lock "$tmp/requirements-dev.lock"
  cp ../ml/requirements-dev.lock "$tmp/ml.lock"
  compile_ml "$tmp/ml.lock"
  diff -u ../ml/requirements-dev.lock "$tmp/ml.lock"
  echo "lock files are up to date"
else
  compile requirements.lock
  compile requirements-dev.lock --extra dev
  compile_ml ../ml/requirements-dev.lock
  echo "wrote backend/requirements.lock, backend/requirements-dev.lock, ml/requirements-dev.lock"
fi
