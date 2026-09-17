\# EcoMind AI - Architecture Decisions



This document records important architectural and engineering decisions.



New decisions must be added rather than silently changing established architecture.



\---



\# ADR-001: Backend Framework



\## Decision



Use Python with FastAPI for the EcoMind AI backend.



\## Reason



FastAPI provides:



\- asynchronous API support

\- automatic OpenAPI documentation

\- Pydantic validation

\- strong Python ecosystem support

\- suitable integration with AI/ML libraries



\## Status



Accepted



\---



\# ADR-002: Primary Database



\## Decision



Use PostgreSQL as the primary database and system of record.



\## Reason



PostgreSQL provides:



\- relational integrity

\- transactions

\- indexing

\- scalability

\- strong SQL support

\- compatibility with geographic extensions such as PostGIS



\## Status



Accepted



\---



\# ADR-003: ORM



\## Decision



Use SQLAlchemy for database access.



\## Reason



SQLAlchemy provides:



\- ORM support

\- transaction management

\- relationship handling

\- database abstraction

\- compatibility with PostgreSQL



\## Status



Accepted



\---



\# ADR-004: Database Migrations



\## Decision



Use Alembic for database schema migrations.



\## Rules



Database schema changes should be represented by migrations.



Never rely on manually modifying production schemas.



Migrations must be safe for existing data.



\## Status



Accepted



\---



\# ADR-005: API Versioning



\## Decision



Use versioned APIs.



Preferred prefix:



&#x20;   /api/v1/



\## Reason



API versioning allows future changes without immediately breaking existing clients.



\## Status



Accepted



\---



\# ADR-006: Authentication



\## Decision



Use JWT-based authentication with secure password hashing.



\## Requirements



\- passwords must be hashed

\- tokens must expire

\- protected endpoints must validate tokens

\- secrets must come from environment configuration

\- sensitive authentication information must not be logged



\## Future Support



The architecture should allow:



\- refresh tokens

\- password reset

\- email verification

\- MFA



\## Status



Accepted



\---



\# ADR-007: Authorization



\## Decision



Use backend-enforced role-based access control.



Initial roles:



\- citizen

\- collector

\- admin



\## Rule



Authorization must not depend on frontend-only checks.



Avoid scattering hardcoded numeric role IDs throughout the application.



Prefer centralized role/permission handling.



\## Status



Accepted



\---



\# ADR-008: Layered Backend Architecture



\## Decision



Use a layered backend architecture.



Preferred structure:



&#x20;   api/

&#x20;   core/

&#x20;   models/

&#x20;   schemas/

&#x20;   services/

&#x20;   repositories/

&#x20;   ai/

&#x20;   integrations/

&#x20;   realtime/



\## Reason



This separates:



\- HTTP/API concerns

\- business logic

\- database access

\- AI functionality

\- external integrations

\- realtime infrastructure



\## Status



Accepted



\---



\# ADR-009: PostgreSQL as Source of Truth



\## Decision



PostgreSQL is the authoritative source for application state.



The following must not be treated as the authoritative source:



\- frontend state

\- browser storage

\- mobile state

\- cached values

\- AI responses



Caches may be used for performance but must not replace persistent application state.



\## Status



Accepted



\---



\# ADR-010: AI Architecture



\## Decision



AI functionality must be separated behind an application-level abstraction.



Potential technologies include:



\- PyTorch

\- scikit-learn

\- Hugging Face

\- Transformers

\- Ollama



\## Reason



The application should be able to replace AI models/providers without rewriting the entire business layer.



\## Status



Accepted



\---



\# ADR-011: AI Predictions



\## Decision



AI predictions should record appropriate metadata.



Potential metadata:



\- model name

\- model version

\- prediction

\- confidence

\- inference time

\- timestamp

\- status



\## Rule



Heuristic confidence values must not be presented as scientifically validated probabilities.



\## Status



Accepted



\---



\# ADR-012: AI Assistant Security



\## Decision



The AI assistant must not have unrestricted application access.



The AI assistant must not directly:



\- execute arbitrary SQL

\- modify arbitrary database records

\- change user roles

\- perform financial transactions

\- execute arbitrary operating-system commands

\- bypass authorization



AI actions must use controlled application services and explicit allowlists.



\## Status



Accepted



\---



\# ADR-013: Waste Classification



\## Decision



Waste classification should support multiple approaches.



Initial/fallback approach may include deterministic classification.



Long-term approach should support real ML/image classification.



Categories include:



\- plastic

\- paper

\- glass

\- metal

\- organic

\- e-waste

\- other



\## Status



Accepted



\---



\# ADR-014: Geographic Routing



\## Decision



Separate road routing from route optimization.



Use OpenStreetMap/OSRM for geographic routing and road-distance information where appropriate.



Use Google OR-Tools for optimization.



\## Reason



Routing and optimization solve different problems.



OSRM can provide realistic road distances and durations.



OR-Tools can solve constrained optimization problems.



\## Status



Accepted



\---



\# ADR-015: Route Optimization



\## Decision



Use structured route and route-stop entities.



Do not represent the entire route as an opaque text field when structured data is required.



A route should support information such as:



\- collector

\- status

\- total stops

\- total distance

\- estimated duration



A route stop should support:



\- route

\- collection

\- sequence

\- latitude

\- longitude

\- estimated arrival

\- distance from previous stop

\- status



\## Status



Accepted



\---



\# ADR-016: Complaints



\## Decision



Complaints are managed inside the EcoMind AI platform.



The system must not automatically submit complaints to government portals.



Future external integrations must use explicit adapters and require actual:



\- APIs

\- authorization

\- credentials

\- permissions

\- agreements



\## Status



Accepted



\---



\# ADR-017: Carbon Credits vs Rewards



\## Decision



Reward points and carbon credits are separate concepts.



Reward points are internal sustainability/reward mechanisms.



Carbon-related records may represent estimates or marketplace simulations.



They must not automatically be represented as legally recognized carbon credits.



\## Status



Accepted



\---



\# ADR-018: External Integrations



\## Decision



External services must be isolated behind adapters/interfaces.



Potential integration categories:



\- AI

\- routing

\- optimization

\- notifications

\- IoT

\- storage



\## Reason



This reduces vendor lock-in and allows fallback implementations.



\## Status



Accepted



\---



\# ADR-019: IoT Architecture



\## Decision



The platform should be IoT-ready without falsely claiming live IoT deployment.



Potential technologies include:



\- MQTT

\- Redis

\- background workers



Smart-bin simulators may be used for development and academic demonstration.



Simulated data must be clearly identified.



\## Status



Accepted



\---



\# ADR-020: Realtime Communication



\## Decision



Use realtime technologies only where they provide meaningful value.



Potential technologies:



\- WebSockets

\- Server-Sent Events

\- Redis

\- background workers



Potential realtime functionality:



\- collection updates

\- route progress

\- collector location

\- notifications

\- smart-bin events

\- environmental alerts



\## Status



Accepted



\---



\# ADR-021: Frontend



\## Decision



Use React and TypeScript for the web frontend.



The frontend must consume backend APIs.



The frontend must not access PostgreSQL directly.



\## Status



Accepted



\---



\# ADR-022: Mobile



\## Decision



Use React Native/Expo for the mobile application where practical.



The mobile application must use the same backend APIs as the web application.



A separate mobile backend should not be created unless a future architectural decision explicitly requires it.



\## Status



Accepted



\---



\# ADR-023: Collector Offline Support



\## Decision



The collector application should be designed for unreliable connectivity.



Where appropriate, support:



\- local caching

\- queued updates

\- synchronization



Server-side state remains authoritative.



Conflicts must be handled explicitly.



\## Status



Accepted



\---



\# ADR-024: Security



\## Decision



Security is a first-class architectural requirement.



Important controls include:



\- authentication

\- authorization

\- password hashing

\- JWT security

\- input validation

\- rate limiting

\- secure file uploads

\- CORS configuration

\- audit logging

\- secret management

\- secure error handling



\## Status



Accepted



\---



\# ADR-025: Secrets



\## Decision



Secrets must be provided through environment configuration.



Never commit:



\- database passwords

\- JWT secrets

\- API keys

\- private tokens

\- OAuth credentials

\- production credentials



`.env.example` may document required variables without containing real credentials.



\## Status



Accepted



\---



\# ADR-026: Audit Logging



\## Decision



Important administrative and security-sensitive operations should produce audit records.



Potential information:



\- actor

\- action

\- entity

\- entity ID

\- timestamp

\- metadata



Secrets and sensitive credentials must never be stored in audit logs.



\## Status



Accepted



\---



\# ADR-027: Demo and Simulation



\## Decision



Simulation is allowed for functionality requiring unavailable external infrastructure.



Examples:



\- smart bins

\- IoT sensors

\- drones

\- government APIs

\- municipal systems

\- live traffic

\- carbon marketplace infrastructure

\- environmental sensors



Simulated functionality must be explicitly identified.



The system must not present simulation as a real-world integration.



\## Status



Accepted



\---



\# ADR-028: Government Integration



\## Decision



Government integration is future-ready architecture only unless an actual authorized integration exists.



EcoMind AI must not claim:



\- government partnership

\- government API integration

\- automatic government complaint submission



without actual verified integration.



\## Status



Accepted



\---



\# ADR-029: Carbon Marketplace



\## Decision



The carbon marketplace may initially be implemented as an academic/software simulation.



The implementation must not represent simulated transactions as legally recognized carbon-market transactions.



Real financial functionality requires a separate security and compliance review.



\## Status



Accepted



\---



\# ADR-030: Git Workflow



\## Decision



Git is the primary project version-control and recovery mechanism.



Development should use focused commits.



Do not:



\- force push

\- rewrite history

\- delete the repository

\- perform destructive resets without explicit approval



Completed logical tasks should be committed.



\## Status



Accepted



\---



\# ADR-031: Claude Session Continuity



\## Decision



Project state must be stored in the repository rather than relying on conversation history.



Persistent project-control files:



\- CLAUDE.md

\- PROJECT\_SPEC.md

\- PROJECT\_STATUS.md

\- DECISIONS.md

\- docs/CLAUDE\_HANDOFF.md



\## Reason



Claude sessions/accounts may change.



The next session must be able to continue using the repository alone.



\## Status



Accepted



\---



\# ADR-032: Phase-Based Development



\## Decision



EcoMind AI will be developed incrementally.



A phase is not complete until:



\- implementation is complete

\- relevant tests pass

\- migrations are complete

\- security is reviewed

\- documentation is updated

\- project status is updated

\- handoff is updated

\- Git checkpoint exists



\## Status



Accepted



\---



\# ADR-033: No Fake Functionality



\## Decision



The project must not use fake functionality merely to make the UI appear complete.



Mock/demo data is allowed only when explicitly identified.



Production functionality must use real backend/database behavior.



\## Status



Accepted



\---



\# ADR-034: API as Integration Boundary



\## Decision



Web and mobile clients communicate through backend APIs.



The backend is responsible for:



\- authentication

\- authorization

\- validation

\- business logic

\- persistence

\- AI orchestration

\- external integrations



\## Status



Accepted



\---



\# ADR-035: Future Scalability



\## Decision



The architecture should be capable of future expansion to:



\- multiple cities

\- large numbers of users

\- multiple collectors

\- high report volume

\- IoT streams

\- multiple AI inference workloads

\- multiple route optimization jobs



However, unnecessary complexity should not be introduced before it is justified.



\## Status



Accepted



\---



\# Future Decisions



New architecture decisions must be added below this section.



Use the following format:



\## ADR-XXX: Title



\### Context



Describe the problem.



\### Decision



Describe the chosen solution.



\### Alternatives Considered



Describe relevant alternatives.



\### Reason



Explain why the decision was made.



\### Consequences



Describe benefits, limitations, and trade-offs.



\### Status



Proposed / Accepted / Superseded

