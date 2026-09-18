# EcoMind-AI Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-01 | A citizen can register/login; elevation via public registration, invalid credentials, inactive users, and invalid JWTs are rejected. |
| AC-02 | Every protected endpoint enforces named role, ownership, and organization scope; cross-user/cross-organization reads and writes are rejected. |
| AC-03 | A citizen can create/view own validated report; location is retained; media handling is safe before upload support is enabled. |
| AC-04 | The canonical `submitted/reviewed/assigned/in_progress/collected/rejected/cancelled` lifecycle has one transition service, backend validation, history where required, and API/UI tests. |
| AC-05 | AI recommendations have validated bounded output, provider/version/confidence/latency traceability, safe fallback behavior, and no executable capabilities. |
| AC-06 | Collection assignment, route access, collector updates, notifications, and idempotent rewards enforce actor and tenant rules. |
| AC-07 | Complaint creation/triage/history/notification enforce ownership and staff permissions. |
| AC-08 | Notifications, rewards, and transactions expose only the current user’s records. |
| AC-09 | Environmental/municipality/IoT records are admin-only, provenance-labelled, and never claim a disabled integration is live. |
| AC-10 | Carbon UI/API remains clearly demonstrative until its excluded compliance scope is approved. |
| AC-11 | Dashboard metrics are backend-calculated and organization-scoped. |
| AC-12 | Important operations create redacted audit events. Any future AI-initiated action uses persisted proposal/pending-review/approve-or-reject/execute/result/audit; rejected or unapproved actions never execute. |
| AC-13 | Security headers/configuration, secret validation, error handling, audit redaction, rate-limit policy, database migration test, backup/restore evidence, and deployment smoke checks meet documented release gates. |
| AC-14 | Web build/lint, mobile typecheck, backend pytest suite, PostgreSQL integration tests, and manual citizen/collector/admin flows pass in CI. |

## Release evidence

No item is accepted merely because an endpoint returns success. Each AC requires
automated tests, an evidence link in the traceability matrix, and current
documentation. Current direct human-admin actions do not need a second approval
queue; AC-12 applies that queue to future AI-initiated actions.
