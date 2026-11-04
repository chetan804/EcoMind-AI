# Integration: Email

Outbound e-mail for account security messages (password reset, e-mail verification, password-changed notices). Called by the `auth` module's service layer through `app.state.email_sender`; routers only schedule the send after the response.

| `EMAIL_BACKEND` | Behaviour | Allowed in production |
|---|---|---|
| `none` | Nothing is sent. `GET /auth/config` reports `password_reset_available: false`, so the UI never promises an e-mail that cannot arrive. | yes (the production default) |
| `smtp` | STARTTLS (default) or implicit TLS, certificate verified, optional login. Needs `SMTP_HOST`, `EMAIL_FROM`, and `APP_BASE_URL` over https. | yes |
| `console` | Writes the full message (including the one-time link) to the log. | **no** (refused at startup) |
| `memory` | Keeps messages in `outbox` for tests. | no (tests only) |

Unset resolves to `none` in production, `console` in local and `memory` in tests.

Rules: plain text only; the log never contains a recipient address or message body for failed deliveries; the one-time token appears only in the message body. No provider SDKs: SMTP covers every common provider (SES, SendGrid, Postmark, Mailgun, self-hosted).

Files: `base.py` (message, protocol, error), `smtp.py`, `console.py` (console + memory), `factory.py` (`build_email_sender`, `deliver`).

## Delivery, retries and logs

`factory.deliver` is what the routers schedule after the response. A **transient** failure (network error,
timeout, server disconnect, 4xx reply: `EmailDeliveryError.transient`) is retried up to 3 attempts in total with
0.5 s and 2 s waits; a **permanent** one (refused recipient, authentication failure, 5xx, bad header) is not.
Structured log lines: `email.delivered`, `email.delivery_retry`, `email.delivery_failed`, each with `purpose`,
`backend` and the attempt count, never the recipient or the body. The retry lives in the worker thread of one
process: **a restart in the middle of a retry loses the message** (no outbox table yet; see
`docs/project-completion/LIMITATIONS.md`).

## What is and is not verified

* Verified by automated tests: the SMTP client against an in-process server (plain text, STARTTLS required,
  header-injection refusal, authentication), the retry policy and the log content.
* **Not verified: delivery through any real provider.** No SMTP credentials exist in this project, so no claim of
  delivery to a real mailbox is made. Local runs use the console backend or Mailpit (`scripts/setup/init_demo_mail.py`).
* Message kinds implemented today: e-mail verification, password reset, password-changed notice (`auth`).
  Invitation, role-request decision and operational notices are in-app notifications only; there is no e-mail template for them.
