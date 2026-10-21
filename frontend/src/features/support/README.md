# Feature: support

Help assistant, support requests and the help articles the assistant quotes.

**Status:** implemented (API: `docs/api/support-api.md`; design: `docs/decisions/ADR-0003-retrieval-help-assistant.md`; quality: `docs/ml/support-assistant.md`).

- **Backend module:** `support`
- **Screens:** `pages/AssistantPage.tsx` (`/assistant`: chat, sources, related articles when nothing is found, feedback, "send to the support team") and `pages/SupportPage.tsx` (`/support`: my requests; for staff the queue, assistant usage and article editor). Tabs follow the signed-in user's permissions (`support:ask`, `support:manage`, `knowledge:manage`); the server enforces them again.
- **Honesty rules the UI keeps:** every assistant reply is labelled with how it was produced (help articles, your account, no answer, not permitted) and lists its sources; replies and tickets are rendered as plain text (never HTML); a chat is shared with staff only if the person ticks the box when sending a request; the page says plainly that the assistant does not write free-form answers.
- **Layout:** `api/`, `components/`, `hooks/`, `pages/` and an `index.ts` that is the feature's only public interface.
