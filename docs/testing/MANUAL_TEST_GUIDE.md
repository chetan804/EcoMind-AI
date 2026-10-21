# EcoMind AI — manual test guide (A to Z)

**Purpose.** You will start the project, sign in as every kind of user, use every feature, and write down what happened. At the end the scorecard (Part 16) tells you whether the project meets your requirements.

**Who this is for.** Anyone. You do not need to program. If you can use a web browser and copy a line into a terminal, you can do this.

**How long.** About 3 to 4 hours for everything. Parts 0–3 are set-up (30–45 minutes). You can stop after any part and continue later.

**What was and was not checked before you.** The steps for Parts 4–14 were rehearsed by an automated browser against a real running copy of the app (see the note at the end of each part where something could not be rehearsed). Where I did not rehearse a step, it says **(not rehearsed)**.

---

## How to read the steps

- Each test has an **ID** (for example `C-3`), **what to do**, and **what you should see**.
- Write **PASS** if what you see matches. Write **FAIL** if it does not, and copy the exact message or take a screenshot.
- Text in `code style` is something to type or a button name exactly as it appears on screen.
- Menu names are the **sidebar** items on the left.
- If a message mentions a **request ID**, write it down; developers use it to find the cause.
- A button that looks greyed out and cannot be clicked is **normal** when a required field is empty. Fill in every field first.

### Use separate browser windows for separate people
Signing in as a second person in the same browser signs the first one out. Use one **normal window** and one **private/incognito window**, or two different browsers. Better still, finish one person's tests, sign out, then sign in as the next.

---

## Part 0 — What you need

1. A computer with **Docker Desktop** (Windows, Mac) or Docker Engine (Linux), and **make** installed. (Git Bash on Windows includes it only if you add it; if `make` is missing, use WSL.)
2. A web browser (Chrome, Edge or Firefox).
3. An **authenticator app** on your phone (Google Authenticator, Microsoft Authenticator, Aegis or 1Password) for Part 6.
4. The project folder `EcoMind-AI`.
5. A text editor for your results (or print this file).

## Part 1 — Start the project

Open a terminal **inside the `EcoMind-AI` folder**.

| Step | Type | You should see |
|---|---|---|
| 1 | `make env` | A `.env` file is created. Do not share it. |
| 2 | `make up` | Docker builds and starts three things: database, server (backend), website (frontend). The first time takes several minutes. |
| 3 | Open `http://localhost:5173` in your browser | The EcoMind AI landing page. |
| 4 | Open `http://localhost:8000/health` | A short message saying the server is healthy. |
| 5 | Open `http://localhost:8000/ready` | A message that the server is ready (it checks the database). |

If a step fails, read `docs/operations/troubleshooting.md`. Common causes: Docker is not running; ports 5173, 8000 or 5432 are already used by another program.

> If you cannot use Docker, use "Option B" in `docs/PROJECT_GUIDE.md` part 11.

## Part 2 — Create the first administrator

Nobody can make the first administrator from the website (this is deliberate). Do it from the terminal.

1. In the browser go to `http://localhost:5173/sign-up`. Create an account: Full name `Test Admin`, Email address `admin.test@example.org`, Password `Test-Passphrase-2026!x`, Confirm password the same, then `Create account`.
2. In the terminal:
   ```
   docker compose exec -e ECOMIND_ADMIN_PASSWORD='Test-Passphrase-2026!x' backend python -m app.cli create-admin --email admin.test@example.org --name "Test Admin"
   docker compose exec backend python -m app.cli seed-support-knowledge
   ```
3. The first command makes that account an administrator. The second loads the 31 help articles the assistant uses. Both should print a confirmation and no error.
4. **(not rehearsed in Docker; the same commands ran in my sandbox without Docker. CI runs them in Docker.)** If the first command says the user exists and asks for something else, read its message; it is explicit.

## Part 3 — Create the test people

You need six accounts. **Sign out between sign-ups** (account menu at the top right → `Sign out`), or use a private window.

Use the **same password** for all: `Test-Passphrase-2026!x`.

| Full name | Email address | Role to give |
|---|---|---|
| Test Admin | `admin.test@example.org` | Administrator (done) |
| Test Manager | `manager.test@example.org` | Manager only |
| Test Collector | `collector.test@example.org` | Collector only |
| Test Operator | `operator.test@example.org` | Facility operator only |
| Test Citizen | `citizen.test@example.org` | Citizen (default, nothing to change) |
| Second Citizen | `citizen2.test@example.org` | Citizen (default) |

**Sign-up steps for each:** go to `/sign-up` → fill Full name, Email address, Password (12 characters minimum), Confirm password → `Create account`. You land on the dashboard with "Good morning, <name>".

> Limit: 10 sign-ups per hour per computer. Six is fine.

**Give roles (as administrator).**
1. Sign out. Sign in at `/sign-in` as `admin.test@example.org`.
2. Sidebar → **Settings** → **Users**.
3. In `Search` type `manager.test`. The user appears. Click `Roles` for that row.
4. In the dialog: **tick `Manager`, untick `Citizen`**, type a `Reason` (for example "Test setup"), click `Change roles`.
5. Repeat for `collector.test` (tick only `Collector`) and `operator.test` (tick only `Facility operator`).

**Expected:** after each change the roles column shows only the new role. Roles are *replaced* by what is ticked.

| ID | Check | Expected | Result |
|---|---|---|---|
| S-1 | Sign-up works for all six accounts | Each lands on the dashboard | |
| S-2 | Roles dialog refuses an empty reason | `Change roles` cannot be completed without a reason | |
| S-3 | Users list shows the right roles | manager = Manager, collector = Collector, operator = Facility operator, citizens = Citizen | |

## What you will see in the sidebar, by role (use this to check Part 4 onward)

| Role | Sidebar items (measured by opening the app as each role) |
|---|---|
| Citizen (13) | Dashboard, Classification, Incidents, Alerts, Facilities, Zones, Marketplace, Reports, Guide, Rewards, Help assistant, Support, Settings |
| Collector (15) | Dashboard, Classification, Collections, Routes, Incidents, Alerts, Vehicles, Facilities, Zones, Marketplace, Reports, Guide, Help assistant, Support, Settings |
| Facility operator (15) | Dashboard, Classification, Review queue, Collections, Alerts, Facilities, Zones, Marketplace, Reports, Guide, Recovery, Traceability, Help assistant, Support, Settings |
| Manager (22) | Dashboard, Analytics, Classification, Review queue, Collections, Routes, Forecasting, Anomalies, Incidents, Alerts, Vehicles, Facilities, Zones, Marketplace, Reports, Guide, Recovery, Traceability, Rewards, Help assistant, Support, Settings |
| Administrator (22) | The same 22 as a manager. In Settings the administrator also has **Audit**. |

Notes: operators have **no Incidents item** and collectors have **no Rewards item** (neither earns points or triages incidents). In the Settings area, Users appears for managers and administrators; Audit only for the administrator.

---

# Part 4 — The public website (not signed in)

Sign out first (or use a private window).

| ID | Do | Expected | Result |
|---|---|---|---|
| P-1 | Open `http://localhost:5173/` | Landing page "Smarter Waste Management for a Cleaner Tomorrow". Four facts: **5** user roles, **6** waste classes, **3** ML capabilities built, **0** classifiers approved for use. A paragraph says the project is under development, **not deployed anywhere yet**, and that no performance or impact figures are published. It must **not** show accuracy or impact numbers. | |
| P-2 | Look for buttons that do nothing | On `/sign-up`, the `Google` and `Microsoft` buttons are **greyed out** with the reason "Single sign-on providers are not available in this build". On the landing page, "Watch demo" is unavailable with "No product demo is available yet". Nothing should look clickable but do nothing. | |
| P-3 | Open `http://localhost:5173/dashboard` while signed out | You are sent to the sign-in page. | |
| P-4 | Open `http://localhost:5173/analytics` while signed out | Sent to sign-in. | |
| P-5 | Open `http://localhost:5173/nonsense` while signed out, then again after signing in | Signed out: you are sent to the sign-in page. Signed in: a "Page not found" page with `Go to the start page`. Never a blank screen. | |
| P-6 | Open `http://localhost:8000/api/v1/facilities` | A JSON error with code about authentication (HTTP 401), not data. | |
| P-7 | `/sign-in` with a wrong password for `citizen.test@example.org` | "Could not sign in" with a neutral message that does not say whether the e-mail exists. | |
| P-8 | Try 5 wrong passwords in a row for the same e-mail | After the fifth, you are temporarily blocked for about 15 minutes. *(Do this last in the whole test, or with a throw-away address, or you will lock yourself out.)* | |
| P-9 | `/sign-up` with a password of fewer than 12 characters | The form refuses it with a message. | |
| P-10 | `/sign-up` with the same e-mail you already used | A refusal that does not crash. | |

# Part 5 — Everyone: shell, theme, system status

Sign in as `citizen.test@example.org`.

| ID | Do | Expected | Result |
|---|---|---|---|
| G-1 | Look at the top of the page | A banner "Confirm your email address" with `Send a new link`. (Normal until verified; see Part 12.) | |
| G-2 | Account menu (top right) | Shows `System status`, a theme toggle, `Sign out`. | |
| G-3 | Click the theme toggle | Whole app switches between dark and light. Reload: the choice is kept. Check text is readable in both. | |
| G-4 | Open `System status` | Shows server and database status in plain words. Citizens do not see administrator-only details. | |
| G-5 | Shrink the browser window to phone width | The sidebar collapses to a menu; pages still usable; nothing runs off the screen sideways. | |
| G-6 | Use only the Tab key on the sign-in page | A visible highlight moves through fields and buttons in a sensible order; Enter submits. | |
| G-7 | Press Esc while a dialog is open (try it in Part 8) | The dialog closes. | |

# Part 6 — Security page: password and two-step verification

Sign in as `citizen.test@example.org`. Account area → **Security** (or Settings → Security).

| ID | Do | Expected | Result |
|---|---|---|---|
| M-1 | Open the Security page | "Two-step verification: Off" and `Set up two-step verification`; a `Change password` form. | |
| M-2 | Click `Set up two-step verification` | A QR code and a field `Code from your app`. | |
| M-3 | Scan the QR code with your authenticator app, type the 6-digit code, confirm | A screen `Save these recovery codes now` with codes. **Copy them somewhere safe.** Status becomes On. | |
| M-4 | Sign out, sign in again | After the password you are asked for an `Authenticator or recovery code`. Enter the app code. You get in. | |
| M-5 | Sign out, sign in, use **one recovery code** instead | You get in. The same code will not work a second time (try it). | |
| M-6 | Enter a wrong code | A clear error; no sign-in. | |
| M-7 | Change password: wrong `Current password` | Refused. | |
| M-8 | Change password: correct current, new password under 12 characters | Refused with a reason. | |
| M-9 | Change password properly, then sign in with the new one | Message "Password changed. Your other devices have been signed out." The old password no longer works. | |
| M-10 | As administrator, Settings → Users, find this user, use `Reset two-step` | Two-step for that user is cleared (the Two-step column changes). The user can sign in with only a password again. | |

> **Important:** if you keep two-step on for an account, keep the app or recovery codes. If you lose both, an administrator must reset it (`docs/operations/account-recovery.md`).
> Remember your new password for `citizen.test` (or change it back).

**Not rehearsed in a browser:** M-3 to M-5 (the code paths are tested by automated tests that compute the codes; a real phone was not used).

---

# Part 7 — Administrator

Sign in as `admin.test@example.org`.

| ID | Do | Expected | Result |
|---|---|---|---|
| A-1 | Sidebar | Same 22 items as a manager. Settings shows `Users` and `Audit`. | |
| A-2 | Settings → Users: filter by `Role` = Collector | Only collector accounts. Try `Search` too. | |
| A-3 | `Deactivate` `citizen2.test` and give a reason | Account shows Deactivated. In a private window, `citizen2.test` **cannot sign in**. | |
| A-4 | `Reactivate` it | Can sign in again. | |
| A-5 | Try to change your **own** roles or deactivate yourself | Refused (the server code is `self_modification_forbidden`: another administrator must do it). Also you can never remove the last active administrator. *(Not rehearsed by hand; documented in `docs/api/administration-api.md`.)* | |
| A-6 | Settings → Audit | A list of events: your role changes, deactivation, etc., each with who, when, what. The role change from Part 3 and the deactivation appear with the reasons you typed. | |
| A-7 | Filter or search the audit list | Works; no errors. | |
| A-8 | System status (administrator) | Shows more detail than a citizen saw. | |
| A-9 | Open Classification | "No classification model is active". This is the **expected, honest** state. | |

**Rehearsed:** role change with reason, audit log shows entries, system status. A-5 was not rehearsed.

# Part 8 — Manager sets up the working data

Sign in as `manager.test@example.org`. These items are the foundation for the later parts. The coordinates below are real-looking Hyderabad values chosen for testing; the facility and vehicle are invented.

### 8.1 Zone
1. Sidebar → **Zones** → `Add zone`.
2. Fill `Code` = `Z-TEST`, `Name` = `Test zone`, `Type` = Residential → `Add zone`.
3. **Expected:** the zone appears in the list as Active with 0 facilities. A note says zones have no map boundaries (honest).

### 8.2 Facility
1. **Facilities** → `Add facility`.
2. Fill `Code` `F-TEST`, `Name` `Test depot`, `Type` Depot, `Status` Active, `Zone` `Test zone (Z-TEST)`, `Address` `Road 1, Madhapur`, `City` `Hyderabad`, `Country code` `IN`, `Daily capacity (kg)` `5000`, `Latitude` `17.4483`, `Longitude` `78.3915` → `Add facility`.
3. **Expected:** it appears in the list. Go back to **Zones**: the zone now shows **1** facility.
   *Tip:* `Use my current location` asks your browser for permission; typing the numbers is simpler.

### 8.3 Vehicle
1. **Vehicles** → `Add vehicle`.
2. `Registration number` `TEST-001`, `Type` Van, `Capacity (kg)` `900`, `Home depot` `Test depot` (the dropdown may take a second to fill) → `Add vehicle`.
3. **Expected:** `TEST-001` appears, status Available.

### 8.4 Sorting guide
1. **Guide** → `Add category`: `Code` `testwood`, `Name` `Test wood` → `Add category`.
2. `Add guidance`: `Material` Test wood, `Disposal method` Reuse, `Title` `Reuse test wood`, `Instructions` `Remove nails and offer it on the marketplace.`, `Source` `Test note` → `Add guidance`.
3. **Expected:** the guidance appears. Sign in as a citizen later: they can read it but have no `Add` buttons.

| ID | Check | Expected | Result |
|---|---|---|---|
| D-1 | Zone created | Appears; 0 facilities | |
| D-2 | Facility created with zone | Appears; zone count becomes 1 | |
| D-3 | Facility with a blank `Name` | `Add facility` stays disabled or the form shows an error | |
| D-4 | Vehicle created | Appears, Available | |
| D-5 | Duplicate registration number `TEST-001` | A clear refusal | |
| D-6 | Guidance created | Appears under the guide | |
| D-7 | Edit the facility (`Edit`), change capacity, save | The new value shows | |

**Rehearsed:** 8.1 to 8.4 creation (zone, facility with zone and coordinates, vehicle, category, guidance). D-3, D-5, D-7 were not rehearsed.

---

# Part 9 — The main workflow, step by step

This is the heart of the project. Do it in this exact order. It involves four people. Use two windows if you can.

### 9.1 Citizen files a waste report
Sign in as `citizen.test@example.org` → sidebar **Reports** → `Report waste`.
- `Title` `Pile of mixed waste near test park`
- `Address or landmark` `Gate 2, Test Park`
- `Estimated weight, kg (optional)` `20`
- `Latitude` `17.4401`, `Longitude` `78.3489`
- Photo (optional): choose a small JPEG, PNG or WebP picture (not larger than the limit shown).
- Click `Submit report`.

**Expected:** the report appears in the list with status **Submitted**. If you attached a photo, opening the report shows it. The citizen sees only their own reports.

### 9.2 Manager reviews and verifies
Sign in as `manager.test@example.org` → **Reports**.
1. Open the new report (the `Open` button on its row). Check the details and photo.
2. Click `Review report`. Set `New status` to **Verified** and click `Save review`. (Choosing Rejected makes `Reason (required)` mandatory.)
3. **Expected:** status becomes Verified. The button `Create collection task` appears (it appears **only** for verified reports).
4. Try this separately later: create a second report and **reject** it. A reason is required and is recorded.

### 9.3 Manager creates the task
1. In the verified report, click `Create collection task`. The "New collection task" form opens with the report's title and address already filled in. Choose a `Priority`, check the `Latitude` and `Longitude` (a task needs coordinates to be placed in a route plan; add them if blank), then click `Create task`.
2. **Expected:** a task appears under **Collections** with status **Pending**, linked to the report.

### 9.4 Manager assigns the collector
1. **Collections** → open the task (`Open`) → `Assign`.
2. Choose `Collector` = `Test Collector`, `Vehicle (optional)` = `TEST-001` → `Assign`.
3. **Expected:** the task shows **Assigned** and the assignee's name.

### 9.5 Manager plans a route (optional but recommended)
1. **Routes** → `Plan a route`.
2. `Plan name` `Test loop`, `Date` any date (**required**), `Start depot` `Test depot`.
3. Under "Tasks to include" tick your task (click its **text**), `Create plan`.
4. Open the plan (`Open`). **Expected:** a draft with the stop order, total distance in km, and a notice **"No road route: straight-line fallback"** (honest: no road data). Click `Publish plan`. Status becomes **Published**.
5. A task already in an active plan cannot be added to another one; the app says so.

### 9.6 Collector does the work
Sign in as `collector.test@example.org` → **Collections**.
1. The assigned task is visible. Open it (`Open`).
2. Click `Start task`. **Expected:** In progress.
3. Optional: `Share my position` (browser asks permission); `Log event` to note something.
4. Click `Complete with weight`, enter `Collected weight (kg)` `12.5` (and optionally a destination and notes), then `Complete task`.
5. **Expected:** the task is **Completed** with **12.5 kg**.
6. The collector cannot create or assign tasks (no `New task` or `Assign`).

> Points are earned **only** when the task was created from a **verified citizen report** and is completed with a weight. A task created directly under Collections (no report) earns nobody points. The collector earns no points.

### 9.7 Citizen sees the result
Sign in as `citizen.test@example.org`.
- **Alerts:** a new notification "Your reported waste was collected" with "12.500 kg collected".
- **Rewards:** the points balance went up by **125** (12.5 kg × 10 points per kg). The ledger shows an **Earned** entry. The page says points come from verified weight only and no carbon claim is made.
- **Reports:** the report is no longer "Submitted"; it reflects the progress.

| ID | Check | Expected | Result |
|---|---|---|---|
| W-1 | Report created | Status Submitted | |
| W-2 | Citizen sees only own report | Another citizen (`citizen2.test`) does not see it | |
| W-3 | Manager verifies | Status Verified; `Create collection task` appears | |
| W-4 | `Create collection task` is absent for an unverified report | Absent | |
| W-5 | Task created from the report | Pending | |
| W-6 | Assign | Assigned; collector receives an alert "New collection task assigned" | |
| W-7 | Route plan created and published | Published; honest fallback note | |
| W-8 | Collector starts and completes with weight | Completed, 12.5 kg | |
| W-9 | Citizen notified | "Your reported waste was collected" | |
| W-10 | Points awarded | +125 points (default 10 per kg) | |
| W-11 | Completing the same task again | Not possible; no double points | |
| W-12 | Collector has no `Assign` or `New task` | Absent | |

**Rehearsed with a browser:** 9.3 to 9.6 (task creation, assignment with vehicle, start and complete with weight, route plan creation and publishing). The automated browser suite also covers 9.1 to 9.7 end to end, including points and the notification. Creating a task *from a report* (button `Create collection task`) was not rehearsed by hand; I rehearsed creating the task from the Collections page (`New task`), which is the same form.

---

# Part 10 — Incidents, marketplace, rewards redemption

### 10.1 Incidents
1. **Citizen:** **Incidents** → `Report an incident`. `Type` Overflowing bin, `Title` `Overflowing bin at Gate 2`, `Address or landmark` `Gate 2`, `Latitude` `17.44`, `Longitude` `78.35` → `Submit incident`. **Expected:** it appears in the citizen's list as Open.
2. **Manager:** **Incidents** → open it (`Open`). Move the status to **Acknowledged** (and optionally assign someone), save. **Expected:** status changes. The citizen gets an alert "Your incident report is now acknowledged".
3. Resolve it (status **Resolved**, with a `Resolution` text). **Expected:** it shows resolved.
4. **Collector** can report incidents and sees their own. (Operators have no Incidents page.) (Known gap: a collector who is *assigned* someone else's incident cannot open it.)
5. Another citizen cannot see this citizen's incident.

### 10.2 Marketplace
1. **Operator** (`operator.test`) → **Marketplace** → `New listing`: `Title` `Offcut wood`, `Category` Wood, `Quantity` `50`, `Unit` kg, `Condition` Good → `Create draft`. **Expected:** a Draft listing visible to its owner only.
2. Open it → `Publish`. **Expected:** Published, visible to everyone.
3. **Citizen** → Marketplace → open the listing → `Request this`. **Expected:** the request is recorded; `My requests` shows it; the citizen can `Withdraw request`.
4. **Operator** → open the listing → the request is listed → `Accept`. **Expected:** the listing becomes **Reserved**. `Release reservation` puts it back; `Mark as handed over` closes it.
5. Another listing: try `Decline`, `Close listing` (it asks for a reason: `Closed because`), and `Renew` on an expired one. Photos can be added through `Manage photos` (images only).
6. A citizen has **no** `New listing` button.

### 10.3 Rewards redemption
1. **Manager** → **Rewards** → `Reward items` tab → `New reward`: `Name` `Test tote bag`, `Cost in points` `100`, `Units in stock` `5`, `Limit per person` `2` → save. **Expected:** it appears in the list. (If a citizen cannot see it later, `Edit` it and check that its status is active.)
2. **Citizen** (with the 125 points from Part 9) → **Rewards** → `Redeem` tab → `Redeem` on the tote bag → confirm.
3. **Expected:** a **claim code** is shown. The balance drops by 100 (to 25). The ledger shows a **Redeemed** entry. Close it and find the code again under `My redemptions`.
4. **Manager** → Rewards → `Redemption queue` → find the redemption → `Hand over` (enter the claim code). **Expected:** status becomes Fulfilled. You may instead cancel it. Afterwards look at the ledger and write down what happened to the points (this was not rehearsed).
5. Try to redeem something that costs more than your balance. **Expected:** refused.
6. Manager `Adjust points` on the ledger: enter a citizen, a number and a note. **Expected:** an **Adjustment** entry appears; the ledger is never edited, only added to.

| ID | Check | Expected | Result |
|---|---|---|---|
| I-1 | Citizen reports incident | Open | |
| I-2 | Manager acknowledges and resolves | Status changes; citizen notified | |
| I-3 | Other citizens cannot see it | Not visible | |
| K-1 | Operator creates and publishes a listing | Published | |
| K-2 | Citizen requests it | Request recorded | |
| K-3 | Owner accepts | Reserved | |
| K-4 | Hand-over | Closed | |
| K-5 | Citizen has no `New listing` | Absent | |
| R-1 | Redeem | Claim code, balance reduced | |
| R-2 | Redeem too much | Refused | |
| R-3 | Staff hand over | Fulfilled | |
| R-4 | Adjust points | Adjustment entry added | |

**Rehearsed with a browser:** incident report and acknowledgement; the browser suite covers marketplace and rewards redemption. Individual `Decline`, `Renew`, photos and cancel-redemption were not rehearsed by hand.

---

# Part 11 — Facility: recovery and traceability

### 11.1 Recovery records
1. **Operator** → **Recovery** → `Record recovery`.
2. `Facility` `Test depot`, `Material` Glass, `Method` Recycled, `Processed on` pick a date and time **not in the future** (a future time is refused with "processed_at cannot be in the future"), `Weight processed (kg)` `100`, `Weight recovered (kg)` `80` → `Record recovery`.
3. **Expected:** a record appears as **Pending**. It is **not counted** in the recovery rate yet.
4. The operator opens it: there is **no** `Verify` button, and the dialog says you cannot verify a record you created.
5. **Manager** → **Recovery** → `Verify` on that row → `Decision` Verify → `Save decision`.
6. **Expected:** Verified. The page's **Recovery rate (verified)** now includes it. The page explains the rate is a mass ratio, not a landfill-diversion or carbon claim.
7. Also test `Reject` on another record.

### 11.2 Material passport
1. **Operator** → **Traceability** → `Create passport`: `Material` Glass, `Weight (kg)` `50`, `Held at` `Test depot` → `Create passport`.
2. Open it (`Open`) → `Record custody event` (for example a transfer) → save. **Expected:** the event appears in the history in order.
3. `Link recovery record`: choose the verified record if a suitable one exists. (If none matches the material, the dialog says "No suitable record exists for this material yet".)
4. `Check integrity`. **Expected:** the result says the history is intact.

### 11.3 Review queue
Operator → **Review queue**. **Expected:** "Nothing is waiting for review". This is correct because no model produces predictions.

| ID | Check | Expected | Result |
|---|---|---|---|
| F-1 | Record created | Pending, not in the rate | |
| F-2 | Creator cannot verify own record | No Verify button | |
| F-3 | Manager verifies | Verified, rate updated | |
| F-4 | Future time refused | Error message | |
| F-5 | Passport created | Appears | |
| F-6 | Custody event added | Appears in order | |
| F-7 | Integrity check | Intact | |

**Rehearsed:** record creation (including the future-time refusal and the required date), verification by a manager, passport creation. Custody events, linking and integrity checking were not rehearsed by hand.

---

# Part 12 — Account recovery and e-mail verification

By default no real e-mail is sent. The program writes the e-mail, including its link, into the **server log**.

1. Show the log: `docker compose logs backend`. Search for `verify-email` or `reset-password` links (the output of `docker compose logs backend | grep -i "http"` helps).
2. **Verify e-mail:** click `Send a new link` in the banner → find the link in the log → paste it in the browser. **Expected:** you see a confirmation page, and the banner disappears. (The page must not confirm by itself on load; a button asks you first.)
3. **Forgot password:** `/sign-in` → `Forgot password` → enter `citizen2.test@example.org` → "Request received" (the same message whether or not the e-mail exists). Find the reset link in the log → open it → choose a new password → "You can sign in with your new password". Sign in with it.
4. Use the same link a second time. **Expected:** refused (single use).
5. In a **production** setup with no e-mail configured, "Forgot password" is hidden and a page explains that reset by e-mail is not enabled; the administrator route is described in `docs/operations/account-recovery.md`.

| ID | Check | Expected | Result |
|---|---|---|---|
| E-1 | Verify link works once | Confirmed, banner gone | |
| E-2 | Reset link works once | New password works, old one does not | |
| E-3 | Unknown e-mail on forgot-password | Same neutral message | |

**Rehearsed:** the automated browser suite runs these four flows (4 tests passed).

---

# Part 13 — Manager and administrator intelligence screens

Sign in as the manager.

### 13.1 Dashboard and analytics
1. **Dashboard:** key numbers (kg collected, open tasks, recovery rate, anomalies), a weekly chart, a status chart, and a map. **Expected:** the kg collected includes your 12.5 kg; the recovery rate includes your verified record. Numbers come from your data, not invented.
2. The map shows a notice **"Base map not installed"** because there is no tile file. Points still appear on a plain background. This is expected.
3. **Analytics:** the "Executive analytics" page loads; each figure states its source.

### 13.2 Forecasting
1. **Forecasting**. The series list contains your platform series and, only if reference data was imported, public series such as Austin and Ballarat.
2. Run the platform series: **Expected: refusal** "At least 26 complete weeks of history are needed to forecast". The app must **not** invent a forecast. (This is the honest behaviour.)
3. If reference data is loaded (needs `import-reference-series`, see `docs/PROJECT_GUIDE.md`), choose `Austin (TX)` and `Run forecast`. **Expected:** a chart with a forecast and bounds, plus a backtest compared with the naive baseline. Lower error than the baseline is better.

### 13.3 Anomalies
1. **Anomalies** → `Scan a series`.
2. With the platform series: "Detection needs more than 12 complete weeks of history". With public data loaded, `Run scan` finds unusual weeks and lists them as alerts labelled "Public reference data".

### 13.4 Support and the help assistant
1. **Citizen** → **Help assistant**. Click one of the suggested questions, for example "How do I redeem my points for a reward?". **Expected:** an answer built from a help article, with its source named.
2. Ask "What is my points balance?". **Expected:** the answer uses **your own** balance.
3. Ask something unrelated ("What is the capital of France?"). **Expected:** "no answer" and an offer to contact support. It must not make something up.
4. Ask for another person's data ("What is citizen2's balance?"). **Expected:** refused as not permitted.
5. `Contact the support team` / **Support** → `New request`: `Subject`, `What do you need help with?` → `Send request`. **Expected:** it appears under `My requests` as Open.
6. **Manager** → **Support** → `Support queue` → open the ticket, reply, and `Change status`. **Expected:** the citizen sees the reply and the new status. `Assistant usage` shows counts. `Help articles` allows `New article` (Published or Unpublished).
7. Citizen cannot see the queue.

| ID | Check | Expected | Result |
|---|---|---|---|
| X-1 | Dashboard numbers reflect Part 9 and 11 | Yes | |
| X-2 | Forecast on empty platform data | Refused, no fake chart | |
| X-3 | Forecast on public data (if loaded) | Chart plus backtest | |
| X-4 | Anomaly scan | Honest result or refusal | |
| X-5 | Assistant answers a documented question | Answer with source | |
| X-6 | Assistant refuses an unknown question | "No answer" | |
| X-7 | Assistant refuses other users' data | Not permitted | |
| X-8 | Ticket created, answered, status changed | Works | |

**Rehearsed:** forecast and anomaly on Austin and Ballarat data, the refusals on empty data, the analytics page; the browser suite covers the assistant and a support request. Help-article editing was not rehearsed by hand.

---

# Part 14 — Who can do what: permission checks

For each row, sign in as the person and try. All "Expected" results are **refusals**. Typing an address directly in the browser is the best way to test it.

| ID | Person | Try | Expected | Result |
|---|---|---|---|---|
| N-1 | Citizen | Open `/analytics` | The page "You do not have access to this page", no data | |
| N-2 | Citizen | Open `/collection`, `/routes`, `/fleet` | "You do not have access to this page" | |
| N-3 | Citizen | Open `/settings/users` and `/settings/audit` | "You do not have access to this page" | |
| N-4 | Citizen | Look for `Add facility`, `Add zone`, `Add vehicle` | Absent | |
| N-5 | Collector | Open `/analytics`, `/forecasts`, `/anomalies`, `/rewards`, `/recovery` | "You do not have access to this page" | |
| N-6 | Collector | Open `/settings/users` | "You do not have access to this page" | |
| N-7 | Operator | Open `/routes`, `/fleet`, `/analytics` | "You do not have access to this page" | |
| N-8 | Operator | Review a waste report (`Review report`) | Absent | |
| N-9 | Manager | Open `/settings/audit` | "You do not have access to this page" (administrator only) | |
| N-10 | Manager | Settings → Users: try `Change roles` | Not available to a manager | |
| N-11 | Manager | Open Classification and look for model management | No model management; "No classification model is active" | |
| N-12 | Any | Sign out, then press the browser Back button | You are not shown private data | |
| N-13 | Two citizens | Citizen 2 opens `Reports` | Does not see citizen 1's reports | |
| N-14 | Any | Reload a page after being deactivated by an administrator | Access is lost | |

**Rehearsed:** all five roles were checked against the live server for every parameterless data address (no server errors; pattern matched the permission table), and a browser crawl opened every sidebar item as each role. The individual typed-address checks above are the same rules seen from the browser.

---

# Part 15 — Optional and advanced checks

These need extra setup. Skip them if you do not intend to use these features.

### 15.1 Forced two-step verification (production rule)
In `.env`, set `ENVIRONMENT=production` plus every other required production setting (the server refuses to start with missing or unsafe values and tells you which; `docs/operations/runbook.md` lists them). Restart. Then sign in as the **manager** or **administrator** who has **no** two-step set up.
- **Expected:** you can sign in, but every other page is blocked with a message that you must **"Set up two-step verification to continue"**, and you are taken to the Security page. After setup, everything works.
- A collector, operator or citizen is **not** forced.
- *(Not rehearsed in a browser; covered by automated API and component tests.)*

### 15.2 Offline map file
Install a regional tile file as `docs/maps/OFFLINE_MAPS.md` explains. **Expected:** streets appear on the map pages and the notice "Base map not installed" disappears. *(Not rehearsed with a real tile file.)*

### 15.3 Google Maps (only if you hold keys)
Set the variables described in `docs/maps/GOOGLE_MAPS_INTEGRATION.md`. **Expected:** Google basemap loads. *(Never tried by me.)*

### 15.4 Live position and the simulator
- With `Share my position`, a collector's phone sends real positions; the manager's **Vehicles** map shows the vehicle only after a real report arrives. A vehicle that never reported must not appear.
- **Simulated vehicles** (a checkbox on the map; the route-plan dialog has a simulator for users with the right permission) must always be clearly labelled "Simulated positions are not real GPS". *(Real GPS: not verified.)*

### 15.5 Quick automated checks
- `python3 tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173` — a fast live check.
- `make test` and `make test-e2e` run the project's own automated tests (they need the developer tools installed).

---

# Part 16 — Your scorecard

## 16.1 Count your results
| Area | Tests | PASS | FAIL |
|---|---|---|---|
| Set-up and accounts (S) | 3 | | |
| Public site (P) | 10 | | |
| Everyone (G) | 7 | | |
| Security page (M) | 10 | | |
| Administrator (A) | 9 | | |
| Manager setup (D) | 7 | | |
| Main workflow (W) | 12 | | |
| Incidents (I) | 3 | | |
| Marketplace (K) | 5 | | |
| Rewards (R) | 4 | | |
| Facility (F) | 7 | | |
| Recovery of accounts (E) | 3 | | |
| Intelligence and support (X) | 8 | | |
| Permissions (N) | 14 | | |
| **Total** | **102** | | |

## 16.2 Must-pass list (the project is not ready if any of these FAIL)
- [ ] S-1, S-3 accounts and roles
- [ ] P-3, P-4, P-6 protected pages and data need a sign-in
- [ ] M-4, M-9 sign-in with two-step and password change
- [ ] W-3, W-5, W-8, W-9, W-10, W-11 the report-to-reward chain with no double points
- [ ] F-2, F-3 the record creator cannot verify their own record
- [ ] X-2, X-6, X-7 the system refuses instead of inventing
- [ ] N-1 to N-10 role limits
- [ ] A-6 audit log records the administrator actions

## 16.3 Honest "not ready" items you should expect to see (these are known, not new bugs)
| Known item | What you will see |
|---|---|
| No approved AI classifier | "No classification model is active"; empty Review queue |
| No map tile file | "Base map not installed" on maps |
| No real e-mail | Links appear only in the server log |
| Not deployed | Everything runs only on your computer |
| Google/Routes/OSRM/GPS unproven | Not covered unless you set them up |
| Collector assigned an incident cannot open it | Known gap |
| A route-plan error mentions an internal ID instead of a plan name | Known small issue |

## 16.4 How to decide
- **Ready for a supervised demo or academic submission:** every must-pass item PASSES, at most a few non-critical FAILs, and the known items above are the only surprises.
- **Ready for a limited pilot with real users:** all of the above **and** you have deployed to a real server (HTTPS, backups, real e-mail), tested again there including Part 15.1, and decided the open owner decisions (`docs/project-completion/PROJECT_AUDIT_REPORT.md` section 10).
- **Ready to rely on AI photo identification:** **No**, until a model is trained on licence-clean data, evaluated, and approved by an administrator. That is a separate piece of work.
- Any FAIL in a must-pass item: stop and report it.

## 16.5 How to report a problem
Write: the test ID, the person you were signed in as, what you did, what you expected, what happened (exact message, request ID, screenshot), the time, and the browser. Server messages in the terminal help: `docker compose logs backend`.

## 16.6 Clean-up
- Stop everything: `make down` (keeps the data). To delete all test data too, ask a developer or read `docs/operations/runbook.md`; do not delete anything you are unsure about.
- Never reuse the test passwords on real services.

## Related documents
`docs/PROJECT_GUIDE.md` (what everything is), `docs/project-completion/PROJECT_AUDIT_REPORT.md` (audit and status).
