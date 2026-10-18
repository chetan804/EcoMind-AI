# Contributing

## Workflow
1. Branch from `development`; keep pull requests focused on one change.
2. Read the architecture documents first: `docs/architecture/component-boundaries.md` and the README of the module/feature you touch.
3. Run `make check lint typecheck test` before pushing (CI runs the same plus end-to-end tests).
4. Update documentation in the same pull request: module README status, `docs/requirements/functional-requirements.md` status, API conventions table, and run `make data-dictionary` when models change.

## Rules
- **Structure:** follow the backend module contract and frontend feature pattern. Create only the files you need; no empty placeholder files or pages. Do not move or rename canonical directories, create a second application root, or change the locked stack without an ADR in `docs/decisions/` (reason, impact, alternatives, migration plan).
- **Boundaries:** a module writes only its own tables; call other modules through their services. Frontend features are imported only through their `index.ts`.
- **Database:** schema changes only via Alembic (`make migration m="..."`), reviewed by hand; never edit a merged migration; never use `create_all()`; never reset a database to make a migration pass; add constraint tests.
- **Tests:** add tests with the code. Never delete, skip or weaken a test just to get green; fix the cause. Database tests use isolated databases only.
- **Data and secrets:** never commit `.env` files, credentials, private data, datasets, model artifacts or notebooks with outputs containing data. Use manifests for datasets and the registry for models.
- **Honesty:** do not describe a feature or model as working/accurate/production-ready without tests or evaluation evidence.
- **Commits:** imperative, descriptive subject ("Add collection task status history"); reference requirement IDs (FR-…) when relevant.

## Code style
Backend: ruff (lint + format), mypy strict, type hints everywhere. Frontend: ESLint, TypeScript strict, function components, TanStack Query for server state, React Hook Form + Zod for forms. `.editorconfig` sets whitespace.
