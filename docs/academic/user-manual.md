# User manual

The web app is at the front-end origin (development: `http://localhost:5173`). Menu entries appear only for
screens your role may use; if you open a page you may not use, the app says so, and the server enforces the
same rule. First administrator: `python -m app.cli create-admin` (see `docs/operations/runbook.md`).

## All roles
- **Sign up / sign in** (`/sign-up`, `/sign-in`). Self-registration always creates a *citizen*. Passwords are
  12 to 128 characters; five failed sign-ins for one e-mail lock sign-in for 15 minutes.
- **Forgot password / verify e-mail** (`/forgot-password`, `/reset-password`, `/verify-email`). A reset link or a
  verification link arrives by e-mail and works once. If the organisation has not configured e-mail delivery, the
  sign-in page says so and an administrator must help.
- **Security** (`/settings/security`). Turn on two-step verification: scan the QR code or type the secret into
  an authenticator app, enter a code to confirm, and **store the ten recovery codes**; they are shown once.
  Two-step verification is **required for administrators and managers in production**: until they enrol they see a
  message and cannot use the rest of the app. Others may enable it voluntarily. Change your password here (it
  signs you out everywhere else).
- **Help assistant** (`/assistant`) and **Support** (`/support`). Ask a question: the assistant answers from the
  help articles or from your own points, reports and requests, and says so when it has no answer; it does not write
  free text and uses no outside service. You can then open a support request (attach the conversation only if you
  tick the option).
- **Maps.** Pages with a map (Dashboard, Facilities, Zones, Vehicles, Routes, Collections, Reports, Incidents) draw
  points on an offline map. Without an installed tile file the map shows a plain background and a notice, which is
  expected. A vehicle marker shows the age of its last position and says STALE when it is old; vehicles
  without any recorded position are not drawn. Positions marked "demonstration only" come from a simulator and are
  not real GPS.
- **Alerts** (`/notifications`). Notifications for your account; the bell shows the unread count.
- **Theme.** Account menu, "Use light theme" / "Use dark theme".

## Citizen
1. **Report waste** (`/reports`): choose "Report waste", describe it, add a photo (JPEG, PNG or WebP), and
   submit. The photo is re-encoded and its location data is removed.
2. **Follow the report.** Status moves from submitted to verified or rejected; a rejection shows the reason.
3. **Classify an item** (`/classify`, if your role has it): upload a photo to get a material suggestion with a
   confidence and sorting guidance. If no model is activated, the page says "no model" rather than guessing.
   Low-confidence results are labelled "needs review". Treat the suggestion as help, not a ruling.
4. **Report an incident** (`/incidents`): illegal dumping and similar, with a photo and place.
5. **Rewards** (`/rewards`): points appear when a task made from your *verified* report is collected
   (10 points per kilogram, rounded). You can redeem points against items that staff have added to the catalogue (the
   catalogue is empty until they do); a redemption shows a claim code, can be cancelled while pending, and is marked
   fulfilled when staff hand the reward over.
6. **Marketplace** (`/marketplace`): browse surplus-material listings, request a quantity, and follow the request. You
   can post your own listing (kg or units, up to four photos); you accept or decline requests to it and mark the
   hand-over. Listings expire and can be renewed. There are no payments or delivery.

## Collector
- **Collections** (`/collection`), **Routes** and **Vehicles** (read only): your assigned tasks and plans. Start a task, add events, **complete it with the
  collected weight**, or mark it failed with a reason. Only tasks assigned to you can be worked. A task's map shows the
  planned point and, if your phone is reporting its position, the recorded path. The browser asks for location
  permission only when you choose "Share my position", and sharing works only while the tab is open.

## Facility operator
- **Review queue** (`/classify/review`): confirm, correct or reject classifier suggestions.
- **Facilities and Zones** (`/facilities`, `/locations`): read-only reference for depots, plants and zones; you can also read collection tasks.
- **Recovery** (`/recovery`): record the input and recovered weight of a batch and its method.
- **Traceability** (`/passports`): add chain-of-custody events (collected, transferred, received, processed);
  "verified" needs a verified recovery record. Use "Check integrity" to re-compute the event hash chain.

## Manager
- **Review queue** (`/classify/review`) and **Reports**: verify or reject reports (a reason is required to
  reject), correct a classification, and turn a verified report into a collection task.
- **Collections:** create, assign a collector and vehicle, cancel, or reschedule a failed task.
- **Routes** (`/routes`): build a plan from pending or assigned tasks (up to 40) for a vehicle; the order is
  by straight-line distance and shows no travel time. Publish or cancel the plan.
- **Fleet and Facilities and Zones:** add or edit vehicles, facilities and zones (retire instead of delete).
  Zones are named areas with **no map boundaries**. The fleet map shows last known positions with their age.
  In a demonstration, "Simulation" controls on a route plan can replay a labelled test track for one vehicle; they
  are visibly marked as not real GPS and can be reset.
- **Forecasting** (`/forecasts`): pick a series; the forecast is shown with the baseline, the model version and
  the data provenance. With fewer than 26 weeks of history it says "insufficient history".
- **Anomalies** (`/anomalies`): "suspected anomalies" with a score; acknowledge, resolve or mark as a false
  positive. A suspected anomaly is not a confirmed incident.
- **Incidents:** acknowledge, assign, resolve or dismiss.
- **Rewards:** adjust points with a reason, or reverse an entry; add, edit and switch off catalogue items; fulfil or
  cancel redemptions.
- **Support:** answer support requests and maintain the help articles the assistant uses.
- **Analytics** (`/analytics`) and the **Dashboard**: figures are live queries; an empty database shows empty
  states, not invented numbers.
- **Sorting guide** (`/sorting-guide`): maintain guidance entries, each with a cited source or the label
  "no source cited".

## Administrator
Administrators hold every permission (see `docs/security/route-permission-matrix.md`). In addition:
- **Users** (`/settings/users`): assign roles, deactivate or activate accounts, reset someone's MFA with a
  reason. **Audit log** (`/settings/audit`): searchable record of who did what. **System status**
  (`/settings/system-status`): version, database and migration state.

## When something looks wrong
`docs/operations/troubleshooting.md`. When reporting a problem, include the `X-Request-ID` response header (or the `request_id` in the error body) of the failing call and the time.
