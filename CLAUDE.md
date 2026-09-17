\# EcoMind AI - Claude Engineering Instructions



\## 1. Project Identity



Project name: EcoMind AI



EcoMind AI is an AI-powered smart waste management and environmental sustainability platform.



The system is intended to connect citizens, waste collectors, administrators, AI services, route optimization, environmental monitoring, sustainability features, and future IoT infrastructure through a secure software platform.



This repository is the persistent source of truth for the project.



Do not rely on previous Claude conversations or chat history.



\---



\## 2. Mandatory Project Files



Before doing any development work, read:



1\. CLAUDE.md

2\. PROJECT\_SPEC.md

3\. PROJECT\_STATUS.md

4\. DECISIONS.md

5\. docs/CLAUDE\_HANDOFF.md



Also inspect relevant existing documentation under:



docs/



The repository and these files are the persistent project memory.



\---



\## 3. Core Engineering Principle



Build EcoMind AI as a real, maintainable software product.



Do not create a superficial demo consisting of hardcoded values, fake API responses, placeholder business logic, or disconnected UI screens.



Use real:



\- database persistence

\- API communication

\- authentication

\- authorization

\- validation

\- service-layer business logic

\- migrations

\- tests

\- error handling

\- logging

\- security controls



The frontend must communicate with the backend APIs.



The backend must communicate with PostgreSQL.



PostgreSQL is the system of record.



\---



\## 4. Existing Repository Rule



This repository may contain partially implemented EcoMind AI functionality.



Before changing existing code:



1\. Inspect it.

2\. Understand it.

3\. Determine whether it works.

4\. Preserve useful working functionality.

5\. Identify architectural problems.

6\. Refactor only when justified.

7\. Do not blindly overwrite existing implementations.



Never delete functionality simply because it is inconvenient.



If replacement is necessary, explain why and ensure equivalent or improved functionality exists before removing the old implementation.



\---



\## 5. Development Workflow



Work incrementally.



Do NOT attempt to build the entire project in one session.



For every development task:



1\. Read project-control files.

2\. Inspect the relevant existing code.

3\. State the current state briefly.

4\. State the exact task being implemented.

5\. Implement one logical task.

6\. Run relevant tests.

7\. Fix failures.

8\. Update documentation.

9\. Update PROJECT\_STATUS.md.

10\. Update docs/CLAUDE\_HANDOFF.md.

11\. Update DECISIONS.md if an architectural decision was made.

12\. Commit the completed work.

13\. Push to the current project branch when appropriate.

14\. Stop after the assigned task.



Do not automatically start the next phase.



\---



\## 6. Git Safety



Git is a project safety mechanism.



Never:



\- force push

\- rewrite Git history

\- delete the repository

\- delete branches unnecessarily

\- use destructive resets without explicit approval

\- overwrite unrelated work

\- commit secrets

\- commit .env files containing credentials



Before making substantial changes:



&#x20;   git status



After completing a logical task:



&#x20;   git status

&#x20;   git diff



Create focused commits.



Use descriptive commit messages.



Do not combine unrelated changes into one commit.



\---



\## 7. Session Continuity



Claude sessions may end because of context, usage, account, or session limitations.



The project MUST remain recoverable without the previous conversation.



Therefore:



\- keep PROJECT\_STATUS.md current

\- keep docs/CLAUDE\_HANDOFF.md current

\- record architectural decisions in DECISIONS.md

\- commit completed work

\- never leave major undocumented work in progress



When a task is completed, the repository should clearly communicate:



\- what is complete

\- what was tested

\- what remains

\- what the next task is

\- any known problems

\- any important decisions



Do not claim to know the exact remaining context or token budget.



If the current session is becoming large, finish the smallest safe logical unit, test it, document it, commit it, and stop.



\---



\## 8. Phase Discipline



EcoMind AI will be developed through phases.



A phase must not be considered complete until:



\- implementation is complete

\- database changes are migrated

\- relevant tests pass

\- security is considered

\- documentation is updated

\- project status is updated

\- handoff is updated

\- Git checkpoint is created



Do not silently skip requirements.



If a requirement cannot currently be implemented, document:



\- why

\- what dependency is missing

\- the intended architecture

\- what can be implemented now

\- what remains for later



\---



\## 9. Backend Architecture



Use:



\- Python

\- FastAPI

\- PostgreSQL

\- SQLAlchemy

\- Alembic

\- Pydantic



Prefer a layered architecture.



Typical structure:



&#x20;   app/

&#x20;       api/

&#x20;       core/

&#x20;       models/

&#x20;       schemas/

&#x20;       services/

&#x20;       repositories/

&#x20;       ai/

&#x20;       integrations/

&#x20;       realtime/

&#x20;       utils/

&#x20;       main.py



Keep routers thin.



Business logic belongs in services.



Database access should not be scattered throughout routers.



Use dependency injection where appropriate.



Use API versioning, preferably:



&#x20;   /api/v1/



\---



\## 10. Database Rules



PostgreSQL is the source of truth.



Use SQLAlchemy models and Alembic migrations.



Never modify the production database schema manually when the change should be represented by a migration.



Every schema change must have an appropriate migration.



Be especially careful when adding:



\- NOT NULL columns

\- foreign keys

\- unique constraints

\- indexes

\- enum-like status fields



For populated tables, use safe migration strategies.



Do not destroy existing data merely to simplify a migration.



Use appropriate indexes and constraints.



Avoid storing structured data as opaque text when relational structure is more appropriate.



\---



\## 11. Authentication and Authorization



Security is mandatory.



Implement secure:



\- password hashing

\- login

\- JWT authentication

\- token expiration

\- authorization

\- role-based access control

\- input validation

\- protected endpoints

\- secure error handling



Primary roles:



\- citizen

\- collector

\- admin



Do not rely on hardcoded numeric role IDs throughout the application.



Prefer centralized role/permission handling.



Design the authorization system so additional roles and permissions can be added later.



Never expose passwords, password hashes, JWT secrets, API keys, or private credentials through API responses or logs.



\---



\## 12. Security Principles



Treat all client input as untrusted.



Protect against:



\- SQL injection

\- XSS

\- CSRF where applicable

\- broken access control

\- IDOR

\- insecure file uploads

\- excessive request abuse

\- credential leakage

\- insecure JWT handling

\- sensitive information disclosure



Use:



\- environment variables

\- secure configuration

\- validation

\- rate limiting where appropriate

\- structured logging

\- audit logging for sensitive operations

\- appropriate CORS configuration

\- secure file handling



Do not place secrets directly in source code.



\---



\## 13. AI Engineering Rules



AI functionality must be real and clearly documented.



Do not claim that a model is trained, deployed, accurate, real-time, or production-ready unless it actually is.



The AI layer should use abstractions so models/providers can be replaced.



Potential ecosystem integrations include:



\- Hugging Face

\- Transformers

\- PyTorch

\- scikit-learn

\- Ollama



AI functionality may include:



\- waste classification

\- image-based waste classification

\- complaint classification

\- complaint severity suggestion

\- environmental analysis

\- sustainability insights

\- AI assistant



AI predictions should store appropriate metadata such as:



\- model name

\- model version

\- confidence

\- timestamp

\- inference status



Do not fabricate confidence values and present them as scientifically validated model probabilities.



If a heuristic fallback is used, label it as a heuristic.



\---



\## 14. AI Safety



AI must not have unrestricted authority over the application.



AI must NOT directly:



\- modify database records without controlled application logic

\- change user roles

\- perform financial transactions

\- bypass authorization

\- execute arbitrary SQL

\- execute arbitrary system commands

\- access secrets



Use controlled service APIs and allowlists.



Validate AI outputs before using them in application workflows.



Clearly distinguish:



\- AI-generated suggestions

\- deterministic application decisions

\- human decisions



\---



\## 15. Route Optimization



Route optimization should separate:



1\. Geographic road routing

2\. Optimization



Use OpenStreetMap/OSRM where appropriate for road distances and routing.



Use Google OR-Tools for optimization problems such as:



\- vehicle routing

\- collection stop ordering

\- capacity constraints

\- time windows

\- multiple collectors where appropriate



Do not pretend to have live traffic data unless an actual traffic source is configured.



Do not claim real-time GPS tracking unless it is actually implemented.



Use adapters so routing providers can be replaced.



\---



\## 16. Real-Time Functionality



Where real-time behavior is required, use appropriate technologies such as:



\- WebSockets

\- Server-Sent Events

\- background workers

\- Redis where justified

\- MQTT for IoT where appropriate



Examples of real-time functionality:



\- collection status updates

\- collector location updates

\- route progress

\- notifications

\- smart-bin events

\- environmental alerts



Do not simulate real-time functionality and present it as a live integration.



Demo/simulation functionality must be explicitly labeled.



\---



\## 17. IoT and Future Integrations



Design for future integration with:



\- smart bins

\- sensors

\- GPS devices

\- drones

\- environmental sensors

\- municipal systems



Use adapters/interfaces.



Do not claim that EcoMind AI is connected to live government infrastructure, city-wide IoT infrastructure, drones, or municipal systems unless an actual integration exists.



Provide simulators/mock providers where useful for development and demonstration.



Clearly label simulated data.



\---



\## 18. Complaints



Complaints must be created and managed inside the EcoMind AI platform.



Do NOT automatically submit complaints to government portals.



Future government integration may be supported through an adapter architecture if appropriate authorization, APIs, partnerships, and credentials become available.



\---



\## 19. Carbon Credits



Carbon credits and reward points are different concepts.



Do not represent internal reward points as legally recognized carbon credits.



The platform may provide:



\- sustainability activity tracking

\- carbon impact estimation

\- internal carbon-related records

\- marketplace functionality



Any real-world carbon-credit trading or verification must be clearly distinguished from a software simulation unless actual verified infrastructure exists.



\---



\## 20. Frontend Rules



Frontend technology:



\- React

\- TypeScript

\- Vite or the established project tooling



The frontend must consume backend APIs.



Do not hardcode dashboard statistics that are supposed to come from the database.



Required user experiences include:



\### Citizen



\- dashboard

\- waste reports

\- create report

\- collections

\- complaints

\- notifications

\- rewards

\- carbon/sustainability

\- profile



\### Collector



\- dashboard

\- assigned collections

\- collection status

\- today's route

\- route details

\- collection history

\- notifications

\- profile



\### Admin



\- dashboard

\- users

\- collectors

\- waste reports

\- collections

\- routes

\- complaints

\- environmental monitoring

\- carbon marketplace

\- rewards

\- analytics

\- notifications

\- audit logs

\- settings



\---



\## 21. Mobile Application



A mobile application should be developed where practical using React Native / Expo.



The mobile application should prioritize:



\- citizen reporting

\- GPS/location capture

\- image upload

\- notifications

\- collector workflows

\- route information

\- collection status

\- offline-friendly collector workflows where appropriate



Do not build a second completely independent backend for mobile.



Mobile and web clients should use the same backend APIs.



\---



\## 22. Testing



Testing is mandatory.



Use appropriate tests for:



\- authentication

\- authorization

\- database behavior

\- API endpoints

\- services

\- AI components

\- route optimization

\- complaints

\- notifications

\- realtime functionality

\- frontend components

\- critical mobile workflows

\- security-sensitive operations



Every new feature should have relevant tests.



Do not mark a feature complete when tests are failing.



\---



\## 23. Error Handling



Use predictable API error responses.



Do not expose internal stack traces or sensitive implementation details to users.



Log useful diagnostic information server-side.



Handle external service failures gracefully.



Examples:



\- AI service unavailable

\- routing service unavailable

\- database unavailable

\- notification provider unavailable

\- IoT provider unavailable



The application should degrade safely where possible.



\---



\## 24. External Services



External services must be isolated behind adapters.



Examples:



&#x20;   integrations/

&#x20;       ai/

&#x20;       routing/

&#x20;       optimization/

&#x20;       notifications/

&#x20;       iot/



The application should not become tightly coupled to a single external provider.



Provide fallback behavior where practical.



Document required API keys and configuration in `.env.example`.



Never commit actual credentials.



\---



\## 25. Documentation



Maintain documentation throughout development.



Relevant documentation includes:



\- architecture

\- API

\- database

\- AI

\- security

\- testing

\- deployment

\- disaster recovery

\- IoT

\- routing

\- sustainability

\- open-source components



Update documentation when implementation changes materially.



Do not wait until the final day to document the system.



\---



\## 26. Open-Source Components



EcoMind AI may integrate with open-source ecosystems such as:



\- Hugging Face

\- Transformers

\- PyTorch

\- scikit-learn

\- Ollama

\- Google OR-Tools

\- OpenStreetMap

\- OSRM

\- FastAPI

\- PostgreSQL



Do not claim formal partnerships unless a formal partnership actually exists.



Document:



\- component

\- purpose

\- version

\- license

\- integration method

\- configuration

\- limitations



\---



\## 27. Environment Configuration



Use:



\- `.env`

\- `.env.example`



Secrets must remain outside Git.



Never commit:



\- database passwords

\- JWT secrets

\- API keys

\- OAuth secrets

\- private tokens

\- production credentials



\---



\## 28. Code Quality



Prefer:



\- readable code

\- explicit names

\- small functions

\- type hints

\- validation

\- reusable services

\- clear abstractions

\- consistent error handling



Avoid:



\- unnecessary duplication

\- giant routers

\- giant functions

\- unexplained magic numbers

\- hardcoded credentials

\- hardcoded production URLs

\- fake database responses

\- unnecessary dependencies



Do not introduce a dependency when the existing stack can solve the problem cleanly.



\---



\## 29. No Fake Functionality



Never create fake functionality merely to make a screen look complete.



If a feature is not implemented, show an appropriate:



\- unavailable state

\- coming-soon state

\- simulation state



Do not disguise mock data as real production data.



If mock/demo data is required for development, label it clearly.



\---



\## 30. Current Task Discipline



Always work on the smallest useful logical unit.



If asked to implement a module:



1\. inspect existing code

2\. design the change

3\. implement it

4\. migrate database if necessary

5\. test it

6\. fix failures

7\. document it

8\. update project status

9\. update handoff

10\. commit

11\. stop



Do not continue into unrelated modules automatically.



\---



\## 31. When a Session Is Ending



Before stopping:



\- ensure the current logical task is either complete or clearly documented

\- run relevant tests

\- update PROJECT\_STATUS.md

\- update docs/CLAUDE\_HANDOFF.md

\- record important decisions

\- check Git status

\- commit completed work where appropriate



The handoff must tell the next Claude session exactly where to continue.



\---



\## 32. New Session Protocol



When a new Claude session starts:



Read:



&#x20;   CLAUDE.md

&#x20;   PROJECT\_SPEC.md

&#x20;   PROJECT\_STATUS.md

&#x20;   DECISIONS.md

&#x20;   docs/CLAUDE\_HANDOFF.md



Then run:



&#x20;   git status



Then inspect the repository.



Do not redo completed work.



Continue only from the documented next task unless the user explicitly changes the priority.



\---



\## 33. Final Verification



Before declaring EcoMind AI complete, verify:



\- authentication

\- authorization

\- database

\- migrations

\- waste reporting

\- AI classification

\- collection workflow

\- geolocation

\- route optimization

\- complaints

\- notifications

\- realtime features

\- environmental monitoring

\- IoT readiness

\- rewards

\- carbon/sustainability

\- analytics

\- admin dashboard

\- citizen dashboard

\- collector dashboard

\- mobile application

\- security

\- testing

\- deployment

\- documentation

\- backup/recovery

\- observability



Perform a final audit against PROJECT\_SPEC.md.



Do not declare completion merely because the application starts.



\---



\## 34. Priority Rule



When requirements conflict, use this priority:



1\. Security

2\. Data integrity

3\. Correctness

4\. Maintainability

5\. Testability

6\. Reliability

7\. User experience

8\. Performance

9\. Convenience



Never sacrifice security or data integrity merely to make development faster.



\---



\## 35. Golden Rule



EcoMind AI must remain understandable and recoverable by another developer or another Claude session.



Every significant implementation decision must leave enough information in the repository for development to continue without access to previous conversations.

