# Feature: auth

The sign-in (`/sign-in`) and sign-up (`/sign-up`) screens.

**Status:** implemented and wired to the backend (`/api/v1/auth/*`). Session handling is not in this feature: it is shared infrastructure in `src/services/session/` (see below).

- **Forms:** `SignInForm`, `SignUpForm` (React Hook Form + Zod, `useMutation`). Server errors map to specific messages: wrong credentials, rate limiting (with the `Retry-After` wait), duplicate email (on the email field), password-policy messages (on the password field), unreachable server. The submit button shows a busy state and ignores clicks while a request is in flight.
- **Redirects:** `RedirectIfSignedIn` keeps signed-in users off these pages and returns them to the page they originally requested. `utils/auth-errors.ts#safeRedirectTarget` accepts only same-site paths (open-redirect protection) and never an auth page.
- **Schemas:** `schemas/auth-forms.ts`. The 12-character minimum mirrors the server policy for early feedback only; the server decides.
- **Unavailable controls:** Google and Microsoft sign-in and "Forgot password?" stay disabled with a reason (`unavailableReason`). No identity provider or password-reset flow exists.
- **Layout:** `AuthCard` (illustration panel + form panel), `AuthIllustration` (original SVG), `SocialButtons`.
- **Public interface:** `import { SignInPage, SignUpPage } from '@/features/auth'`.

## Where the session lives

| Piece | Location |
|---|---|
| Session store (token in memory, single-flight refresh, sign-in/up/out) | `src/services/session/session-store.ts` |
| `useAuth()` (status, user, `can(permission)`) | `src/services/session/useAuth.ts` |
| Typed auth API calls | `src/services/session/auth-api.ts` |
| Route guards | `src/app/guards/RequireAuth.tsx`, `RequirePermission.tsx` |
| 401 → refresh → retry once | `src/services/api-client.ts` (`configureAuthHooks`) |

Security properties (tested in `tests/unit/session-store.test.ts` and `tests/e2e/specs/auth.spec.ts`):
the access token is kept in memory only; the refresh token is an HttpOnly cookie JavaScript cannot read; concurrent refreshes share one request; a 401 is retried exactly once; the query cache is cleared when a session ends; a sign-out in one tab signs out the others.

`can()` and `RequirePermission` are a usability layer. The server authorises every request.
