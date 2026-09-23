# Operations runbook

## Service topology (reference deployment)

| Component | What to watch | Where |
| --- | --- | --- |
| `web` (nginx) | 5xx rate, latency | `docker compose logs web` |
| `api` (uvicorn) | request errors, job queue depth | `docker compose logs api` (JSON logs with `request_id`) |
| `db` (PostgreSQL) | connections, disk, backups | `docker compose exec db psql -U ecomind` |

Health: `GET /health` on the API (used by Docker). Every response carries a
`request_id`; the same id appears in logs — grep it to follow one request end-to-end.

## Background jobs

Jobs live in the `jobs` table and are claimed with `SELECT … FOR UPDATE SKIP LOCKED`
by the embedded worker (safe to run multiple). Registered handlers include:

| Job | Trigger | Notes |
| --- | --- | --- |
| Route optimization | `POST /routes/generate` above the inline stop threshold | OR-Tools solve in worker |
| AI batch classification | report/complaint intake (async path) | provider or labelled baseline |
| SLA escalation sweep | periodic | promotes overdue complaints, notifies |
| Sustainability recompute | manual (`POST /sustainability/recompute`) or scheduled | idempotent per period |
| Demo telemetry simulator | only when `ECOMIND_ENABLE_DEMO_SIMULATOR=true` | writes `is_simulated=true` rows only |

Operational queries:

```sql
-- queue depth by status
SELECT status, count(*) FROM jobs GROUP BY status;
-- stuck jobs (claimed but old)
SELECT id, handler, claimed_at FROM jobs WHERE status='running' AND claimed_at < now() - interval '15 minutes';
```

## Common runbooks

### Rotate a compromised device key
`POST /api/v1/iot/devices/{id}/rotate-key` (alert:manage) — old key stops working
immediately; the new key is returned once. Audit entry written automatically.

### Suspend a member
`PATCH /organizations/current/members/{user_id}` with `{"is_active": false}` — their
permissions fail on the next request; refresh tokens can also be revoked via logout
family revocation on password reset.

### Investigate a cross-tenant concern
1. Pull the `request_id` from the report.
2. `SELECT * FROM audit_events WHERE request_id = '…'` — shows actor, action,
   before/after.
3. The tenant-isolation test suite (`pytest tests/test_tenant_isolation.py`) is the
   regression gate — run it on any suspected regression before anything else.

### Re-seed the demo environment (destructive, demo org only)
```bash
cd backend && ./venv/bin/python scripts/seed_demo.py --reset
```

### Backups
```bash
# database
docker compose exec db pg_dump -U ecomind ecomind | gzip > backup-$(date +%F).sql.gz
# uploads (media objects)
docker run --rm -v ecomind-ai_uploads:/data -v $PWD:/backup alpine \
  tar czf /backup/uploads-$(date +%F).tar.gz -C /data .
```
Restore order: stop api → restore DB → restore uploads → start api (entrypoint runs
migrations, which are forward-only; restore to a matching schema version).

### Rate limits
Tune per category with `ECOMIND_RATE_LIMIT_*` (see `.env.example`). The limiter is
in-process — for multi-replica deployments, front the API with a shared limiter
(roadmap: Redis-backed limiter, ADR-0008).

## Alerts worth wiring (external)

- API 5xx rate > 1% for 5 minutes
- `SELECT count(*) FROM jobs WHERE status='failed'` growing
- DB disk > 80%; connection saturation
- Open IoT alerts (`/iot/alerts?status_filter=open`) above threshold — the platform
  generates these alerts; paging/escalation to humans is a deployment concern.

## Upgrade procedure

1. Backup DB + uploads (above).
2. Build new images (`docker compose build`).
3. `docker compose up -d` — the API entrypoint applies Alembic migrations on boot.
4. Watch `GET /health` and logs; roll back by redeploying the previous image tag
   with a restored DB if needed.
