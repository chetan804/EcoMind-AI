# Backup, restore and rollback

What is stored where, how to back it up, how to restore it, and what a rollback costs. Everything marked
**drilled** was run in the development sandbox on 2026-10-20 against the seeded demonstration database
(PostgreSQL 16.2, 35 tables, 2,371 rows, Alembic head `0009`); everything else is a procedure that has
**not** been exercised here (no production environment exists).

## What holds state

| Store | Contents | Backed up with |
|---|---|---|
| PostgreSQL | every table in [data-dictionary.md](../database/data-dictionary.md), including users, audit log, chain-of-custody events and the reward ledger | `pg_dump` |
| File storage (`FILE_STORAGE_LOCAL_PATH`) | uploaded report and incident photos; the database only holds their metadata and checksums | file-level copy of the directory |
| Classifier artifact (`ml/artifacts/`, git-ignored) | model files named by the registry entry; hashes are verified at load | rebuild from the documented command or copy the directory |
| `.env` / secret store | `SECRET_KEY`, database password | the secret store, never Git |

Keep the **database dump and the media directory from the same moment**: a report row points at a photo by
id and checksum, and a restore with a newer database and an older media directory leaves dangling photos
(the API then returns 404 for the image, it does not invent one).

`SECRET_KEY` must be restored with the data: authenticator secrets and recovery-code hashes depend on it,
so data restored under a different key gives affected users `409 mfa_secret_unreadable` until an
administrator resets their MFA ([mfa.md](../security/mfa.md)), and everyone is signed out.

## Backup

```bash
# custom-format dump: compressed, restorable selectively, no owner assumptions
pg_dump --format=custom --file=ecomind-$(date -u +%Y%m%dT%H%M%SZ).dump "$DATABASE_URL_WITHOUT_DRIVER_SUFFIX"
tar -C "$FILE_STORAGE_LOCAL_PATH" -czf media-$(date -u +%Y%m%dT%H%M%SZ).tgz .
sha256sum ecomind-*.dump media-*.tgz > SHA256SUMS      # store the sums beside the files
```

Run at least daily, keep copies off the database host, and restore-test them (below): a backup that has
never been restored is not evidence of anything. Retention and encryption at rest are an operator decision
that this repository does not make.

## Restore (drilled)

```bash
createdb ecomind_restore
pg_restore --no-owner --exit-on-error -d ecomind_restore ecomind-<stamp>.dump
```

Drill result: dump 241,782 bytes in 0.08 s, restore in 0.29 s with `--exit-on-error`; all 35 tables had
identical row counts and `alembic_version` was `0009` in both databases. Then, before using the restored
database, point the backend at it and check `GET /ready`.

## Rollback of a release

1. **Application only (no migration in the release):** redeploy the previous images. Nothing else changes.
2. **Release with a migration:** take a backup first. The previous application version is not guaranteed
   to run against a newer schema, so the safe order is: stop the new backend, restore the pre-release dump
   (loses everything written since) **or** run `alembic downgrade <previous revision>` (loses only what the
   downgraded migration stored), then start the previous images.

`alembic downgrade` is **destructive for data the migration introduced**. Drilled on the restored copy:
`downgrade 0008` then `upgrade head` worked, and afterwards `zones` had 0 rows and no facility had a zone
(the 4 demonstration zones and 3 assignments were gone, as expected). Do not downgrade without a dump.
The append-only triggers of migration `0007` stop the application from updating or deleting audit,
chain-of-custody and reward-ledger rows; the drilled `pg_restore` of the whole database still succeeded,
so a restore is the supported way to bring that history back.

The migration round trip (`upgrade head`, `downgrade base`, `upgrade head`) and `alembic check` are
exercised on a throw-away database by the backend integration tests on every CI run.

## Never

- Reset or drop a database to make a migration pass; write a corrective migration.
- Restore over a running production database; restore to a new database, verify, then switch.
- Commit dumps, media or `.env` files (`.gitignore` excludes them; the dump contains personal data).
