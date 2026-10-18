# Non-functional requirements

Targets marked *target* are goals to be measured when features exist; they are not claims about the current system.

| ID | Area | Requirement | How verified |
|---|---|---|---|
| NFR-SEC-1 | Security | Passwords hashed with Argon2id; no plaintext or reversible storage. | `backend/tests/security/test_passwords.py` |
| NFR-SEC-2 | Security | Server-side validation and authorization on every protected endpoint; deny by default. | security tests per module |
| NFR-SEC-3 | Security | No secrets in the repository, images or frontend bundle; templates contain placeholders only. | `scripts/quality/check_env_templates.py` in CI |
| NFR-SEC-4 | Security | Errors never leak stack traces, SQL or settings. | `backend/tests/api/test_error_handling.py` |
| NFR-SEC-5 | Security | Production refuses to start with weak secret key, wildcard CORS or insecure refresh cookie. | `backend/tests/unit/test_config.py` |
| NFR-CFG-1 | Configuration | All environment-specific values come from environment variables validated at startup. | config tests |
| NFR-DB-1 | Data integrity | Schema changes only via Alembic; models and migrations never drift; invariants enforced by database constraints. | `test_migrations.py`, `test_schema_constraints.py` |
| NFR-DB-2 | Data integrity | Timestamps are timezone-aware UTC; quantities have explicit units. | schema review, data dictionary |
| NFR-OPS-1 | Operability | Liveness independent of dependencies; readiness reflects database and migration state. | `backend/tests/api/test_health.py`, integration readiness tests |
| NFR-OPS-2 | Operability | Every request carries a correlation id in responses, errors and logs; JSON logs available. | `test_error_handling.py` |
| NFR-PERF-1 | Performance (*target*) | List endpoints are paginated (max 100 per page) and filter columns are indexed; typical API reads p95 < 300 ms at expected load. | load test once endpoints exist |
| NFR-REL-1 | Reliability | Cross-module business operations are atomic (single transaction). | service integration tests |
| NFR-MNT-1 | Maintainability | Fixed module contracts; lint, format and strict type checks pass in CI. | CI |
| NFR-TST-1 | Testability | Database tests run on isolated throw-away databases; no shared state. | `tests/fixtures/database.py` |
| NFR-ML-1 | ML integrity | No model is presented as accurate without a reproducible evaluation on held-out data; confidence is model-supplied. | `docs/ml/evaluation-protocol.md` review |
| NFR-PRV-1 | Privacy | No personal or private data in datasets, logs or fixtures. | review |
| NFR-A11Y-1 | Accessibility (*target*) | UI meets WCAG 2.2 AA: semantic landmarks, labelled controls, keyboard access, sufficient contrast. | component tests with role queries; manual audit |
| NFR-COMP-1 | Compatibility | Latest two Chrome/Firefox/Safari/Edge versions; responsive from 360 px. | Playwright (Chromium today) |
| NFR-DEP-1 | Deployability | Frontend and backend deploy independently; migrations run as a separate release step. | `docs/architecture/deployment-architecture.md` |
