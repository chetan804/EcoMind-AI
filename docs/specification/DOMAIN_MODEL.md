# EcoMind-AI Domain Model

## Authoritative entities

```text
Organization 1--* User *--1 Role
User 1--* WasteReport 1--0..1 WasteCollection *--0..1 CollectionRoute
CollectionRoute 1--* RouteStop *--1 WasteCollection
User 1--* Complaint *--0..1 WasteReport
Complaint 1--* ComplaintStatusHistory
User 1--* Notification
User 1--1 RewardAccount 1--* RewardActivity
User 1--* CarbonCredit 1--* CarbonTransaction
Municipality 1--* ServiceArea; Municipality 1--* MunicipalSyncLog
EnvironmentalSource 1--* EnvironmentalReading; SmartBin is independent today
User 0..1--* AIOperationLog
```

## Entity responsibilities

| Entity | Purpose and key relationships |
| --- | --- |
| Organization | Tenant/scoping root. Present but nullable across the current model; tenant invariants remain a security requirement. |
| Role, User | Identity, named authorization role, active status, and optional organization. Password hashes never leave the API. |
| WasteReport | Citizen-owned operational record: type, description, location/coordinates, image reference, lifecycle, and optional AI metadata. One optional collection. |
| WasteCollection | Operational assignment of one report to zero/one collector, schedule, collection lifecycle, and optional route stop. |
| CollectionRoute, RouteStop | A generated ordered plan for a collector and its collection stops; distances/durations are estimates. |
| Complaint, ComplaintStatusHistory | Citizen complaint, optional report link/assignee, lifecycle and immutable per-complaint state-history records. |
| Notification | User-owned in-app event message and read timestamp. |
| RewardAccount, RewardActivity | User points balance and idempotency-keyed reward activity. |
| CarbonCredit, CarbonTransaction | Demonstrative sustainability ledger shape. It is not a verified financial/regulatory carbon-credit system. |
| EnvironmentalSource, EnvironmentalReading, SmartBin | Admin-managed reference/telemetry-ready records. Observed vs estimated/simulated provenance is required before live claims. |
| Municipality, ServiceArea, MunicipalSyncLog | Municipal reference data and sync-event record; current sync is internal placeholder behavior. |
| AIOperationLog | AI invocation metadata/summary only. It is not the generic operational audit event required by FR-12. |

## Proposed-but-not-yet-authorized entities

`AuditEvent` is required for important operations. `ApprovalRequest` and
`ApprovalDecision` are required before any future AI-initiated action. They
must be additive, reference actor/action/target/request context/result, omit
secrets, and be introduced through Alembic. They are not part of the
implemented schema and must not be silently added.

## State ownership

- Report lifecycle transitions are backend service concerns. The canonical
  report vocabulary is `submitted`, `reviewed`, `assigned`, `in_progress`,
  `collected`, `rejected`, and `cancelled`; collection scheduling/progress must
  remain collection data rather than undocumented report states.
- Complaint status transitions are domain-service concerns and retain their own
  history.
- AI classifications are recommendation attributes, not authoritative report
  state or executable commands.
- Only an approved workflow service may move a future AI-initiated action from
  pending review to execution.

## Integrity and boundary rules

- Every resource lookup that exposes or mutates an entity must enforce actor
  role, ownership, and organization scope in the API/service layer.
- Monetary/environmental validity must not be inferred from the carbon schema.
- Coordinates must remain validated geographic values; existing textual
  location data must be preserved.
- Model provider output must map to a Pydantic/domain enum before persistence.
