# ADR-0007: Same-origin SPA — HashRouter, reverse proxy, relative API URLs

**Status:** Accepted · **Date:** 2026-09

## Context

The frontend must work in development, behind nginx in Docker, and from plain
static file serving — without a CORS dance, and without server-side rewrite rules
for client routes.

## Decision

- Browser code calls **relative URLs only** (`/api/v1/…`). In dev, Vite proxies
  `/api`, `/docs`, `/openapi.json` to the backend; in production, nginx does the
  same — the SPA and API are always same-origin.
- Use **HashRouter** (`/#/app/report`) instead of the browser history API.
- Auth tokens live in memory (plus the active-org id in localStorage); the API
  client does single-flight refresh on 401.

## Rationale

- Same-origin removes CORS as a failure surface and simplifies security (cookies
  are not needed; bearer headers suffice).
- HashRouter means any static host serves the app with zero configuration — deep
  links just work, including from `file://` previews.
- In-memory tokens shrink the XSS blast radius versus localStorage-persisted
  tokens.

## Consequences

- URLs carry `#`; if history-style URLs are ever required, the swap is a one-line
  router change plus a server fallback rule (documented in DEVELOPMENT.md).
- Logout/tab-refresh re-authenticates via the refresh flow (still in memory via
  the SPA session; acceptable trade-off for this product's threat model — see
  SECURITY.md for the reasoning).
