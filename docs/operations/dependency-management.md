# Dependency management and supply-chain controls

What is pinned, what is audited, how to upgrade, and what is **not** covered.

## What is pinned

| Area | Source of truth | How CI and the image install it |
|---|---|---|
| Backend (runtime) | `backend/requirements.lock` | `pip install --require-hashes -r backend/requirements.lock` (backend image) |
| Backend (runtime + dev tools) | `backend/requirements-dev.lock` | `pip install --require-hashes -r backend/requirements-dev.lock` then `pip install --no-deps -e backend` (Backend CI, contract job) |
| ML (training, evaluation, tests) | `ml/requirements-dev.lock` | `pip install --require-hashes -r ml/requirements-dev.lock` (ML job) |
| Frontend | `frontend/package-lock.json` | `npm ci` |
| End-to-end tests | `tests/e2e/package-lock.json` | `npm ci` |
| GitHub Actions | commit SHA in each workflow, version in a trailing comment | – |
| CI runner | `ubuntu-24.04` (no `ubuntu-latest`) | – |

The Python lock files are *universal*: one file covers Python 3.11 and 3.12 on every platform (environment markers select the right wheel), and every artefact is hash-verified. `pyproject.toml` stays the human-edited list of direct dependencies with compatible ranges; the lock files are generated from it.

## Upgrading Python dependencies

```bash
pip install uv                         # once
make lock-backend                      # re-resolves keeping current pins; picks up pyproject changes
# to upgrade on purpose, add --upgrade or --upgrade-package NAME to the uv commands in
# scripts/dependencies/lock_backend.sh, run it, then:
make install-backend-locked
cd backend && pytest && ruff check . && mypy
git diff backend/requirements*.lock ml/requirements-dev.lock   # review every version change
```

`make check-locks` (also a CI step in *Quality gates → Structure, templates and Compose*) fails when `pyproject.toml` / `ml/requirements-dev.txt` and the lock files disagree, so a dependency cannot be added without updating the lock.

`backend/lock-constraints.txt` holds one constraint with the reason written next to it (`ai-edge-litert` pulls `backports.strenum` unconditionally, and its newest release only supports Python < 3.11).

## Audits

`scripts/security/run_audits.sh` (also `make audit`) is what the **Security** workflow runs on every push and pull request, and every Monday 03:17 UTC:

| Check | Scope | Fails on |
|---|---|---|
| `pip-audit` | backend and ML lock files (`--require-hashes --strict`) | any known vulnerability in a pinned package |
| `npm audit` | `frontend/`, `tests/e2e/` (dev dependencies included) | high or critical |
| `bandit` | `backend/app` | medium severity or higher |
| CodeQL (`security-extended`) | Python, JavaScript/TypeScript | findings are reported in the Security tab |

The scheduled run exists because a lock file that audited clean on the day it was written can become vulnerable later. When it goes red: upgrade the package, or - if no fixed version exists - document the advisory, the reachability analysis and an expiry date in `docs/security/security-review.md` before adding a time-boxed ignore to the script.

Dependabot (`.github/dependabot.yml`) opens weekly grouped pull requests for GitHub Actions, the two npm projects and the Compose file. It cannot rewrite the Python lock files or discover `backend.Dockerfile`; Python upgrades therefore follow the procedure above.

## Known gaps (owner action or follow-up)

- **Base images are tagged, not digest-pinned** (`python:3.12-slim`, `node:22-alpine`, `postgres:16-alpine`, nginx). The registry is not reachable from the development sandbox, so digests could not be resolved and recorded honestly. Pin them with `docker buildx imagetools inspect <image>` and review them on the same weekly cadence as the other upgrades.
- **No container image scan** (Trivy/Grype) and **no DAST** are configured yet.
- **Licence review** of transitive packages is not automated.
- CodeQL needs GitHub code scanning to be available for the repository (it is for public repositories) and the *default setup* to be disabled, because an advanced workflow and the default setup cannot both upload analyses.
