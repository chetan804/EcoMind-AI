# Accessibility report (2026-11-04)

**What was run (automated, in a real Chromium against the real stack):** axe-core 4.x through
`@axe-core/playwright` with the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`. Serious and
critical violations and every `color-contrast` finding fail the test. Map canvases (third-party) are excluded.

| Spec | Covers | Result |
|---|---|---|
| `tests/e2e/specs/accessibility.spec.ts` | 26 signed-in pages as an administrator (includes security, access requests, users, audit), dark and light theme | passed |
| `tests/e2e/specs/accessibility-public.spec.ts` (new) | landing, sign-in, sign-up, forgot-password, reset-password, verify-email and the open walkthrough dialog; dark and light; 1440 px and 390 px wide | passed after one fix (below) |
| `tests/e2e/specs/role-homes.spec.ts` (new) | the dashboard home of a citizen, collector, facility operator and manager; dark and light | passed |
| `tests/e2e/specs/keyboard.spec.ts` | skip link, visible focus on every Tab stop, no focus trap, account menu, page search dialog, phone navigation drawer, keyboard navigation and sign-out | passed |
| `tests/e2e/specs/ui-shell.spec.ts` | no horizontal scroll at phone width on public and signed-in pages; drawer traps Escape | passed |

Full end-to-end run on 2026-11-04 (scratch database, demo accounts): **59 passed, 6 skipped** before the two new
specs were added; the new ones then passed on their own (public: 4 tests; role homes: 1 test). The 6 skips need
Mailpit or an enforced-MFA configuration that this sandbox does not run; they are skips, not passes.

## Defect found and fixed

`/sign-up`: the hint line ("Instant access" / "Needs approval") on the **selected** account-type card had
insufficient contrast on its tinted background (axe `color-contrast`, serious; dark and light, both widths).
Fix: the hint steps up from the muted to the secondary text colour on the selected card
(`frontend/src/features/auth/auth.css`). The registry row is D20 in
[the defect register](../project-completion/DEFECT_REGISTER.md).

## What this does NOT show

Automated rules find roughly a third of accessibility problems. **Not done and owner-pending:** a human review with a
screen reader (NVDA, VoiceOver), keyboard review of every form and table, zoom and text-spacing checks, reduced-motion
review, and a documented conformance statement. The checklist is in
[ACCESSIBILITY_MANUAL_CHECKLIST.md](ACCESSIBILITY_MANUAL_CHECKLIST.md). Pages reachable only by roles other than
administrator (for example the collector's other screens) were scanned only as administrator, apart from the four dashboard homes.
