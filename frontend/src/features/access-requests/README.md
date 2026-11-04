# Feature: access-requests

Roles and role requests: the "Access and roles" settings page (own roles, request form, own requests, role guide) and the administrators' review queue shown on the Users page.

**Status:** implemented. Backend module `access_requests` (`docs/api/access-requests-api.md`).

- `roles.ts` explains the five account types. It grants nothing: the server enforces permissions and refuses self-assigned roles.
- Public sign-up always creates a Citizen. Operational roles are requested here (or from the sign-up form, which sends the same request after the account exists) and an administrator approves or rejects.
- Other code imports `@/features/access-requests`, never its internals.
