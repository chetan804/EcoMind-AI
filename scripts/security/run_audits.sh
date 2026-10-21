#!/usr/bin/env bash
# Dependency and static-security audits. The Security workflow runs exactly these commands.
#
#   scripts/security/run_audits.sh            everything
#   scripts/security/run_audits.sh python     pip-audit (backend and ML lock files) only
#   scripts/security/run_audits.sh node       npm audit (frontend and e2e) only
#   scripts/security/run_audits.sh bandit     bandit only
#
# Needs: pip-audit and bandit on PATH (pip install pip-audit bandit), npm for the node audits.
# Thresholds (a finding at or above the threshold fails the run):
#   pip-audit   any known vulnerability in a pinned dependency (backend + ML lock files)
#   npm audit   high or critical, including development dependencies
#   bandit      medium severity or higher (the 13 low-severity findings are the subprocess/assert
#               style notes that Ruff's S rules already police; see docs/security/security-review.md)
# A vulnerability with no available fix must be documented in docs/security/security-review.md
# and, only then, ignored with an expiry date in the relevant command below.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
target="${1:-all}"
status=0

run() {
  echo "::group::$*"
  if ! "$@"; then
    status=1
    echo "FAILED: $*"
  fi
  echo "::endgroup::"
}

python_audit() {
  for lock in backend/requirements-dev.lock ml/requirements-dev.lock; do
    run pip-audit --requirement "$lock" --require-hashes --disable-pip --strict
  done
}

node_audit() {
  for dir in frontend tests/e2e; do
    run npm --prefix "$dir" audit --audit-level=high
  done
}

bandit_scan() {
  run bandit --recursive backend/app --severity-level medium --quiet
}

case "$target" in
  python) python_audit ;;
  node) node_audit ;;
  bandit) bandit_scan ;;
  all) python_audit; node_audit; bandit_scan ;;
  *) echo "usage: $0 [all|python|node|bandit]" >&2; exit 2 ;;
esac

if [[ $status -ne 0 ]]; then
  echo "One or more audits failed." >&2
fi
exit $status
