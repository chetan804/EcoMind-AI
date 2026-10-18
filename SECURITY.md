# Security policy

## Reporting a vulnerability
Please **do not open a public issue** for security problems. Report privately through GitHub's "Report a vulnerability" (Security tab → Advisories) on this repository, or contact the maintainer listed on the repository profile. Include affected component, reproduction steps and impact. You will receive an acknowledgement; fixes are coordinated before disclosure.

## Scope
The backend API, frontend, container images and CI configuration in this repository. The project is in its foundation stage and has no production deployment.

## Never commit
Secrets, credentials, `.env` files, private data, datasets or model files. If a secret is committed, treat it as compromised: rotate it first, then remove it from history.

## Baseline
See `docs/security/security-baseline.md` for authentication strategy, configuration rules and required controls.
