# Decision log

Decisions taken during the autonomous build, newest last. Architectural ones have an ADR in `docs/decisions/`. "Owner" items still need the project owner; everything else was decided under the instruction to choose production-grade options without asking.

| # | Date | Decision | Reason | Alternatives rejected | Where |
|---|---|---|---|---|---|
| 1 | 2026-10 | Modular monolith on FastAPI + PostgreSQL; no Redis, broker, Celery, Kubernetes, PostGIS | Locked stack; one deployable unit is enough for the verified requirements | Microservices, queues | ADR-0001 |
| 2 | 2026-10 | Never activate an ML model that is not verified; ship the classifier as a *candidate*, non-default | Honest metrics: TrashNet accuracy 0.867 but 0.454 on RealWaste; 64% of images routed to a person | Marking it production-ready | `docs/ml/model-cards/`, `model_registry/` |
| 3 | 2026-10 | No RealWaste (CC BY-NC-SA) or TrashBox (no licence) data in any released model; TACO unusable (0 of 1,500 images eligible) | Production-level, licence-clean choice | Training on them "for research" and shipping | `docs/ml/dataset-research/` |
| 4 | 2026-10 | Offline map (MapLibre + PMTiles) is the default; Google Maps is opt-in; keys only in env, server key never in the bundle | The owner wants no key and no third-party dependency; Google's terms forbid copying its map | Google-only; scraping tiles | ADR-0002, `docs/maps/` |
| 5 | 2026-10 | Road routing is optional (`ROUTING_PROVIDER=none\|google\|osrm`), nothing stored, never invented | Straight lines are labelled as such; an OSRM server is a documented opt-in deviation | Always-on routing service | ADR-0002 |
| 6 | 2026-10 | Tracking never shows a stationary coordinate as a live vehicle; simulator data is separate and labelled | Honesty contract for operations staff | Showing last-known as live | `docs/api/tracking-api.md` |
| 7 | 2026-10 | Rewards are a hand-over workflow with claim codes; impact is kilograms only, no carbon factor | No sourced coefficient exists; no payment or partner integration is justified | Inventing a CO2 factor | `docs/api/rewards-api.md` |
| 8 | 2026-10 | Supply chain: actions pinned by SHA, hash-locked dependencies, audits in CI | Reproducible builds; base images cannot be digest-pinned from this sandbox (registries unreachable) | Floating tags | `docs/operations/dependency-management.md` |
| 9 | 2026-10 | Registration rate limit is a setting (default 10/IP/hour), relaxed only in the disposable CI stack | CI end-to-end failed with 429s; production default must stay strict | Raising the production limit | `backend/app/core/config.py` |
| 10 | 2026-10-21 | The help assistant is retrieval-only (quotes articles, reads own data, says "I don't know") | No LLM provider/key/data agreement; cannot hallucinate; private; testable offline | Hosted or self-hosted LLM | ADR-0003 |
| 11 | 2026-10-21 | Assistant answers need an anchored match (title or keyword) and 60% query coverage; near misses are only suggested | Body-only coincidences ("time", "name") produced false answers (held-out 2 of 16) | Lower threshold; ranking only | `docs/ml/support-assistant.md` |
| 12 | 2026-10-21 | A chat is shared with staff only when the requester ticks a box; staff reading it is audited; idle chats are purged after 90 days unless attached to a request | Privacy by default | Always attach the chat | `docs/api/support-api.md` |
| 13 | 2026-10-21 | MFA stays optional for all roles in this phase | Enforcing it needs an enrolment-only session state and a rollout plan (existing admins, recovery); doing it half-way would lock people out or add a bypass | A quick "required" flag checked only in the UI | LIMITATIONS.md |
| 14 | 2026-10-21 | Evaluation sets for the assistant are reported as author-written and, for the held-out one, contaminated | Overstating quality would mislead operators | Presenting the numbers as accuracy | `docs/ml/support-assistant.md` |

## Open owner decisions
1. Merge PR #12 (draft) and the support work on it.
2. Google keys for live verification of Google Maps/Routes (not needed for the offline default).
3. Whether the TrashBox authors permit use (otherwise it stays excluded).
4. GitGuardian "Generic Password" finding on a test file: dismissal is owner-only.
5. Whether to add a generative layer to the assistant, with which provider, and under what data-processing terms.
6. Whether and when to require MFA for administrators and managers.
7. The real SMTP server and the sender address for account and support e-mail (nothing has been delivered through real SMTP).
