# Manual accessibility checklist (keyboard and screen reader)

**Status of this document: a blank test form. No row below has been executed by a person.** Automated checks
(axe in `tests/e2e/specs/accessibility.spec.ts`, keyboard behaviour in `tests/e2e/specs/keyboard.spec.ts`)
catch a subset of problems; they do not replace the human pass below, and nothing in this project may be
described as "screen-reader tested" until the **Result** column has been filled in by a named tester.

## How to run it

1. Start the stack ([supervised-demo.md](../operations/supervised-demo.md)) and sign in with the demo accounts.
2. Pick at least one screen reader and browser pair from the table. Record exact versions.
3. For every row write **PASS**, **FAIL** (with what you heard or saw) or **N/A**, plus your name and the date.
4. Any FAIL on rows marked **must** blocks an accessibility claim; open an issue with the row id.

| Pair | Platform |
|---|---|
| NVDA + Firefox, NVDA + Chrome | Windows |
| VoiceOver + Safari | macOS / iOS |
| TalkBack + Chrome | Android |

Tester: ______  Date: ______  Screen reader and version: ______  Browser and version: ______  OS: ______

## A. Keyboard only (no pointer, screen reader off)

| Id | Check | Must | Result |
|---|---|---|---|
| K1 | The first Tab stop on every page is the "skip to main content" link and Enter moves focus into the page | must | |
| K2 | Every interactive element can be reached with Tab / Shift+Tab, in an order that matches the visual order | must | |
| K3 | A visible focus indicator is present on every stop (links, buttons, inputs, menu items, map controls) | must | |
| K4 | No keyboard trap anywhere, including the map, the account menu and dialogs | must | |
| K5 | The page-search dialog and the account menu open from the keyboard, close with Escape and return focus to the control that opened them | must | |
| K6 | The sidebar drawer on a 360 px wide window opens, traps focus only while open, closes with Escape | must | |
| K7 | Forms: Enter submits, labels are reachable, an invalid submit moves focus to the first error or announces it | must | |
| K8 | Sign in, register, forgot password, reset password, two-step verification (code entry and recovery code) are all completable | must | |
| K9 | File a waste report including photo selection, then review it as a manager | must | |
| K10 | Data tables: you can reach row actions and pagination controls | should | |
| K11 | Map pages: every function offered by the map (select a bin or vehicle, see its details) is also available from a list or table | must | |

## B. Screen reader

| Id | Check | Must | Result |
|---|---|---|---|
| S1 | Each page has one `h1`, headings are in a sensible order, landmarks (banner, navigation, main) are announced | must | |
| S2 | Every form field announces its label, required state and hint; errors are announced when they appear | must | |
| S3 | Status messages are announced without moving focus: sign-in failure, save success, "model not available", review-needed notices | must | |
| S4 | Buttons and links have meaningful names (no "click here", no unlabeled icons); the current page is announced in the sidebar | must | |
| S5 | Classification result: the category, confidence, the "human review required" state and the no-active-model message are all announced | must | |
| S6 | Support assistant: the question field, the reply, the cited article titles, and the "no answer found" state are announced in order | must | |
| S7 | Tables announce column headers; badges and status chips are text, not colour alone | must | |
| S8 | Dialogs announce a title and return focus on close; decorative images are ignored, informative images have text | must | |
| S9 | Map: the alternative list/table and the labels "simulated", "last known position" and "offline basemap" are announced | must | |
| S10 | Charts on the dashboard and forecasting pages have a text or table alternative | should | |

## C. Visual and preference checks

| Id | Check | Must | Result |
|---|---|---|---|
| V1 | 200 % browser zoom and a 320 px wide viewport: no horizontal scrolling of the main content, no clipped controls | must | |
| V2 | Text contrast is readable in both themes (use a contrast checker on any suspect pair and write the ratio) | must | |
| V3 | With the operating-system "reduce motion" setting on, no essential animation remains | should | |
| V4 | Text-only zoom to 200 % (browser setting) does not hide labels | should | |
| V5 | Windows high-contrast / forced-colours mode: focus and borders remain visible | should | |

## D. What automation already covers (for context only)

* `accessibility.spec.ts`: axe-core (WCAG 2.0 to 2.2 A/AA tags) over all 22 signed-in routes in both themes, as an
  administrator; fails on serious or critical findings and on any colour-contrast finding. Map canvases are excluded.
* `keyboard.spec.ts` (7 tests): keyboard sign-in, skip link, visible focus on every Tab stop, no trap, account
  menu, search dialog, navigation drawer and sign-out from the sidebar.
* Unit tests in `frontend/tests/` cover labels and roles of individual components.

None of that exercises a real assistive technology, so sections A to C stay open until people run them.

## Reporting results

Copy this file's tables into the issue or the release record, fill them in, and update the accessibility
line of [RELEASE_CHECKLIST.md](../project-completion/RELEASE_CHECKLIST.md) and the "Not verified" list in
[LIMITATIONS.md](../project-completion/LIMITATIONS.md) only with what was actually observed.
