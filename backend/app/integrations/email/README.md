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
