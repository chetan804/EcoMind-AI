# EcoMind-AI User Journeys

## J-01 Citizen registration and sign-in

1. Citizen registers with name, email, and password; public registration cannot
   choose an elevated role.
2. API validates input, hashes the password, persists the citizen, and returns
   a safe profile.
3. Citizen submits OAuth2 password-form credentials and receives a JWT.
4. Web/mobile client uses the token only for authenticated API calls.

**Completion:** invalid credentials/roles fail; inactive accounts fail; no
password hash is returned.

## J-02 Citizen report

1. Citizen submits type, description, textual location, optional coordinates,
   and optional future media reference.
2. API creates a citizen-owned report and awards the documented report reward.
3. Citizen views only own reports and their backend-derived status.
4. Classification is advisory; human review and operations follow
   `submitted → reviewed → assigned → in_progress → collected`, or a terminal
   `rejected`/`cancelled` outcome.

**Approval point:** AI cannot execute classification/review/assignment. A
future AI-initiated operation must enter persisted pending review.

## J-03 Collector collection work

1. Administrator selects an eligible collector and report for collection.
2. Collector sees only assigned collections/routes.
3. Collector updates allowed collection states; API validates transition and
ownership, updates the report as applicable, and notifies the citizen.
4. Completion earns the configured reward exactly once.

**Approval point:** the administrator is the authorized human decision-maker.
A future AI-initiated assignment or route dispatch requires pending review.

## J-04 Complaint resolution

1. Citizen submits a complaint, optionally for an owned report.
2. API records a bounded AI categorization/priority recommendation and initial
history record.
3. Administrator reviews, optionally assigns, transitions status, records a
resolution, and the citizen receives a notification.

**Approval point:** AI output is advisory; the administrator makes the triage
decision. Any future AI-initiated triage action requires pending review.

## J-05 Administrator operations and insight

1. Administrator views organization-authorized reports, collections, routes,
   complaints, environmental/municipal reference records, and analytics.
2. Administrator performs only permitted state/configuration changes.
3. Backend records audit events for important actions once FR-12 is
implemented, without secrets or sensitive payloads.

**Completion:** every result is organization-scoped and request-correlated.

## J-06 Guidance assistant

1. Authenticated user submits a guidance question.
2. Backend supplies only minimum allowed context (current report count/role in
   current code), invokes a safe fallback/provider adapter, and returns display
   text.
3. The answer does not execute any action or override domain decisions.

**Completion:** malformed/unavailable provider output falls back or fails
safely; no sensitive context is exposed.

## J-07 Environmental and smart-bin administration

1. Administrator creates sources/bins and adds readings through API.
2. UI displays data with provenance labels.
3. Live ingestion/sync is only enabled after adapter credentials, device
authentication, observability, and explicit product approval.

## J-08 Sustainability records

1. User views reward balance/activity and demonstrative carbon records.
2. Administrator may create authorized demonstrative entries under the current
API.
3. Any purchase/issuance/retirement that makes financial or verified carbon
claims is out of scope until methodology, approval, settlement, and compliance
requirements are approved.
