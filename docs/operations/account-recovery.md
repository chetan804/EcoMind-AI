# Account recovery: password reset and e-mail verification

Implemented in `backend/app/modules/auth/recovery.py`, `backend/app/integrations/email/` and the web app routes `/forgot-password`, `/reset-password` and `/verify-email`. API reference: `docs/api/auth-api.md`.

## Behaviour

| Flow | Trigger | Result |
|---|---|---|
| Password reset | "Forgot password?" on the sign-in page, or `POST /auth/password-reset/request` | E-mail with a one-time link, valid 30 minutes (`PASSWORD_RESET_TOKEN_MINUTES`). The link opens a form for the new password |
| E-mail verification | Sent on registration; "Send a new link" in the banner shown to unverified users; `POST /auth/email-verification/request` | E-mail with a one-time link, valid 24 hours (`EMAIL_VERIFICATION_TOKEN_HOURS`). Opening the link shows a button; selecting it confirms |
| Password-changed notice | After a reset, and after "change password" in Settings → Security | A plain e-mail without a link |

## Security properties

- **Tokens:** 256-bit random, stored only as a SHA-256 digest (`account_tokens.token_hash`). A database read cannot be turned into a working link.
- **One use, one live link:** a link works once; asking for a new one invalidates the previous one. Replaced, used and expired links all produce the same `400 invalid_or_expired_token`.
- **No account enumeration:** the request endpoints answer `202` with one fixed body for existing, unknown, deactivated and malformed addresses, and when an address is throttled. The mail is queued after the response, so mail-server latency does not leak anything either.
- **Rate limits** (from `audit_logs`, so they hold across workers): 3 messages per address per hour (silently, to avoid leaking), 10 requests per IP per hour (`429`), 20 rejected links per IP per 15 minutes (`429`).
- **Fragment tokens:** the token is in the URL fragment (`#token=`), which is not sent to servers or in `Referer`, and the web app removes it from the address bar after reading it.
- **Click to confirm:** the verification page needs a button press, so link scanners that open URLs cannot consume the link.
- **A reset ends every session** (all refresh tokens revoked), clears the sign-in lockout and sends a notice. **It does not disable two-factor authentication**: the next sign-in still asks for the authenticator code, so a mailbox compromise alone is not enough. A user who lost both password and authenticator needs an administrator (`POST /api/v1/admin/users/{id}/reset-mfa`).
- **Verification via reset:** completing a reset proves control of the mailbox, so it also marks the address verified.
- **Audit:** `auth.password_reset_requested` (with `message_queued`), `auth.password_reset_completed`, `auth.email_verification_requested` (and `auth.email_verification_on_register` for the automatic first link, which is not counted against the request limits), `auth.email_verified`, `auth.account_token_rejected` (with a reason). Addresses appear only as SHA-256 digests; tokens never appear.
- **Delivery failures** are logged (`email.delivery_failed purpose=… backend=…`, never the recipient or the body) and never fail the request or reveal anything to the caller.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `EMAIL_BACKEND` | none in production, console in local, memory in tests | `none`, `console` (log only, refused in production), `smtp` |
| `EMAIL_FROM` | – | Sender, for example `EcoMind AI <no-reply@example.org>` (required for smtp) |
| `APP_BASE_URL` | `http://localhost:5173` | Where links point. **https is required in production** when sending |
| `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_SECURITY` (`starttls`/`ssl`/`none`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_TIMEOUT_SECONDS` (10) | – | `none` is refused in production; username and password must be set together; certificates are verified |
| `PASSWORD_RESET_TOKEN_MINUTES` | 30 | 5–120 |
| `EMAIL_VERIFICATION_TOKEN_HOURS` | 24 | 1–168 |
| `EMAIL_VERIFICATION_REQUIRED` | false | Refuse sign-in until the address is verified. Refused at startup when no e-mail backend works |

Invalid combinations stop the application at startup with a precise message (see `backend/tests/unit/test_config.py`).

### With no e-mail backend (the production default)

`GET /auth/config` reports `password_reset_available: false`; the web app then says "Password reset by e-mail is not enabled" instead of showing a form that cannot work, and the verification banner is hidden. Recovery falls back to an administrator. This is deliberate: **nothing in this repository claims that e-mail works until a real SMTP server has been configured and tested.**

### Local development

The local Compose stack runs with `ENVIRONMENT=local`, so the console backend prints each message, including its link, to the backend log:

```bash
docker compose logs -f backend | grep -A12 "EMAIL (console"
```

### Demo inbox with Mailpit (no real provider)

For a supervised demo where people should *see* the message arrive, the Compose file has an optional
[Mailpit](https://mailpit.axllent.org/) catcher. It accepts every message and shows it in a web inbox;
nothing leaves the machine.

```bash
make demo-mail-up        # creates .env.demo-mail (random SMTP credentials, git-ignored) and starts the stack
# inbox: http://localhost:8025   (backend: EMAIL_BACKEND=smtp, SMTP_HOST=mailpit, port 1025)
python3 scripts/setup/init_demo_mail.py --rotate   # new credentials; then `make demo-mail-up` again
make demo-mail-down
```

This path uses `SMTP_SECURITY=none` inside the Compose network, which the backend refuses when
`ENVIRONMENT=production`; that is intended, because Mailpit is a demonstration tool. Not verified in
this repository: running the Mailpit container itself (the build environment has no Docker). What was
verified: the SMTP settings reach the adapter, the browser suite's Mailpit client logic (see below), and the adapter against an independent SMTP server
(`scripts/demo/verify_smtp_local.py`: STARTTLS and mandatory AUTH succeed; a wrong password and an
untrusted certificate are both refused).

### How the browser tests read the mail

`tests/e2e/specs/account-recovery.spec.ts` takes the one-time links from a mail source chosen by environment
variable (`tests/e2e/specs/mail.ts`):

| Variable | Source | Used by |
|---|---|---|
| `E2E_MAILPIT_URL` (e.g. `http://localhost:8025`) | The Mailpit inbox API (`/api/v1/search`, `/api/v1/message/{ID}`) | CI: the e2e job starts the stack with `--profile demo-mail` |
| `E2E_MAIL_LOG_FILE` (a path, e.g. `/tmp/api.log`) | The backend's console log, read directly from that file (regular file, at most 64 MiB; nothing is executed). Refused when `CI` is set | Local runs with plain `make up`, after redirecting the backend output or saving `docker compose logs --no-color backend > /tmp/api.log` |

With Mailpit the suite also asserts what the log cannot show: the message really arrived over SMTP from a
client that authenticated (`Username` is non-empty), the sender is the configured `EMAIL_FROM`, the token is in
the `#token=` fragment and not the query string, the "password was changed" notice arrives and contains no link,
and an unknown address receives nothing at all. The spec is skipped (and says why) if neither variable is set. The helper never starts a process or builds a command from
configuration (an earlier version ran a shell command from a variable; that was removed as unsafe, and
`tests/contract/test_e2e_no_shell_execution.py` keeps it removed). `tests/e2e/specs/mail.unit.spec.ts` (20 tests, no browser or
stack needed) covers missing or malformed configuration, wrong recipients, malformed messages, missing links, timeouts and
Mailpit failures.

Verification status of this path: the client logic and the spec were run locally against a small stand-in that
speaks SMTP with mandatory AUTH and serves the Mailpit REST shapes from its published OpenAPI document (the real
backend sent through it; both mail sources passed 4/4). **The real Mailpit container has never been run by me**
(no Docker, no download access here); its first execution is the CI e2e job.

### Verified against a real mail server?

Tested locally: the SMTP adapter against a protocol-level server inside the unit tests (message structure, header-injection refusal, connection failure, STARTTLS refusal when unsupported) and the whole flow in a real browser with the console backend. **Not tested: delivery through a real provider (TLS handshake with a real certificate, authentication, spam filtering, SPF/DKIM/DMARC alignment).** Before enabling in production: configure the provider, send a test reset to a mailbox you control, and publish SPF and DKIM records for the sending domain.

## Operating it

```bash
# Housekeeping: delete tokens that expired or were used more than 7 days ago (run daily)
python -m app.cli purge-account-tokens

# Enable EMAIL_VERIFICATION_REQUIRED on a system that already has users.
# Existing accounts are NOT marked verified by the migration (nobody proved those mailboxes),
# so either let users verify through the link, or attest them yourself (audited):
python -m app.cli mark-email-verified --all-existing
python -m app.cli mark-email-verified --email someone@example.org
```

Accounts created with `create-admin` are marked verified (an operator with shell access made them). Users created through registration start unverified.

## Limits (stated, not hidden)

- E-mail change is not implemented (users cannot change their address), so "address changed after the link was sent" only arises from direct database edits.
- Verification is not required by default, and nothing in the application currently *restricts features* for unverified users except the optional sign-in requirement.
- The per-address/IP limits count requests, not deliveries; a throttled address is not told.
- Messages are plain text, English only, with no unsubscribe mechanism (they are transactional security messages).
- Timing: the unknown-address path skips one insert, so a very precise attacker with many samples might measure a difference below network noise. The background send removes the dominant (SMTP) difference.
