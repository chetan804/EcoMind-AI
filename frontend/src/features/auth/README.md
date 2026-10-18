# Feature: auth

Sign in (`/sign-in`) and sign up (`/sign-up`) screens.

**Status:** UI implemented (Stage 1 UI milestone). **There is no authentication.** The forms validate input, but a valid submission sends nothing and shows a "not available yet" message. There are no sessions, tokens, guards or role checks.

- **Backend module (future):** `auth` (see `docs/security/security-baseline.md`).
- **Schemas:** `schemas/auth-forms.ts` (React Hook Form + Zod). The 12-character password minimum is **provisional**: the security baseline leaves the password policy to the sign-up milestone, and it must be confirmed there.
- **Unavailable controls:** Google and Microsoft sign-in and "Forgot password?" are disabled with reasons (`unavailableReason`). No provider has been chosen or configured.
- **Layout:** `AuthCard` (illustration panel + form panel), `AuthIllustration` (original SVG), `SocialButtons`, `SignInForm`, `SignUpForm`. Control sizes are larger than the app default by design (~66 px, from the reference).
- **When the backend exists:** add `api/` and mutation hooks, put the single authentication implementation in this feature plus `app/guards`, and remove the unavailable notices that no longer apply.
- **Public interface:** `import { SignInPage, SignUpPage } from '@/features/auth'`.
