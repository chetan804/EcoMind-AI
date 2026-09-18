# EcoMind-AI Traceability Matrix

`Planned` means the source requirement is locked but not yet demonstrated by
the current implementation/test suite. It is not a completion claim.

| Requirement | Module | API / UI | Data | Test evidence | Acceptance |
| --- | --- | --- | --- | --- | --- |
| FR-01 | `core/security`, `api/users`, `api/auth` | `/users`, `/auth/login`; web/mobile login | User, Role | Partial `test_services`; API tests planned | AC-01 |
| FR-02 | `core/roles`, `core/security` | All protected endpoints; API clients | User.organization_id, Role | Role helper unit tests; BOLA tests planned | AC-02 |
| FR-03 | reports service/router | `/waste-reports`; citizen report UI/mobile report | WasteReport | Schema unit test; endpoint/DB tests planned | AC-03 |
| FR-04 | report/collection services | report and collection status routes/UI | WasteReport, WasteCollection | Transition unit tests; canonical-lifecycle migration/API tests planned | AC-04 |
| FR-05 | `app/ai`, AI integrations | `/classification`, `/complaints`, `/assistant/ask` | AI metadata, AIOperationLog | Baseline AI unit tests; invalid-provider tests planned | AC-05 |
| FR-06 | collection/route services | `/collections`, `/routes`; collector/admin views | WasteCollection, CollectionRoute, RouteStop | Lifecycle/routing unit tests; tenant/API tests planned | AC-06 |
| FR-07 | complaint service/router | `/complaints`; citizen/admin views | Complaint, ComplaintStatusHistory, Notification | Analyzer unit test; endpoint tests planned | AC-07 |
| FR-08 | reward/notification/carbon services | `/notifications`, `/rewards`, `/carbon` | Notification, Reward*, Carbon* | Reward/carbon unit tests; ownership tests planned | AC-08 |
| FR-09 | environmental/municipality modules | `/environmental`, `/municipalities`; admin UI | Environmental*, SmartBin, Municipality* | Municipality unit test; API/provenance tests planned | AC-09 |
| FR-10 | carbon service/router | `/carbon`; sustainability UI | CarbonCredit, CarbonTransaction | Carbon service unit tests; labeling/workflow tests planned | AC-10 |
| FR-11 | analytics service/router | `/analytics`; dashboard | Reports, collections, complaints | No organization/endpoint tests | AC-11 |
| FR-12 | Planned audit service; future approval workflow | Planned audit API/UI; future approval UI | Planned AuditEvent; future Approval* | No current audit coverage; future approval tests planned | AC-12 |
| NFR security/operations | config/main/deployment | `/health`, `/liveness`, `/readiness` | PostgreSQL/Alembic | Build/lint/unit compilation; integration/restore tests planned | AC-13 |
| NFR quality | tests/frontend/mobile/CI | All clients | N/A | 19 unittest tests; no CI/pytest/browser/mobile run | AC-14 |

## Resolution traceability

| Resolution | Affected rows | Locked outcome |
| --- | --- | --- |
| RC-01 lifecycle vocabulary | FR-03, FR-04, FR-06; AC-03, AC-04, AC-06 | `PROJECT_SPEC.md` statuses are canonical; implementation-only report states need a safe migration plan. |
| RC-02 human approval | FR-04 through FR-12; AC-12 | Current AI is advisory and human-admin actions execute under RBAC; future AI-initiated actions require persisted approval. |
| RC-03 claims | FR-09, FR-10; AC-09, AC-10 | Realtime is experimental; carbon is demonstrative only until separately approved. |
