# Development Plan

## Delivery Rules

- Work in small phases with tests at each boundary.
- Establish tenant isolation before adding organization-owned CRUD.
- Keep FastAPI routes thin and business logic in `backend/app/services`.
- Add Pydantic schemas for API contracts.
- Add SQLAlchemy models, Alembic migrations, and tests for persistence changes.
- Do not expose a voice webhook publicly before provider verification,
  idempotency, output escaping, and safe fallback are implemented.

## Phase 1: Development Baseline

- Fix existing backend syntax and import issues.
- Pin dependencies and create reproducible lock or constraints files.
- Make backend tests, linting, type checks, and frontend builds run in CI.
- Separate liveness and readiness checks.
- Add structured configuration validation without committed secrets.

Exit criteria: a clean checkout can install, build, and test using documented
commands, and CI enforces the same checks.

## Phase 2: Identity and Tenant Foundation

- Define users, organization memberships, roles, organizations, and branches.
- Implement trusted request tenant context.
- Add SQLAlchemy session management and initial Alembic migrations.
- Require tenant scope in services and repositories.
- Add cross-tenant read, write, search, cache, and background-job tests.

Exit criteria: organization-owned data cannot be accessed without an
authorized membership and matching tenant context.

## Phase 3: Approved Knowledge

- Add tenant-scoped knowledge CRUD and source metadata.
- Define draft, approved, disabled, and archived lifecycle states.
- Add keyword and semantic retrieval restricted to approved tenant content.
- Return source identifiers and retrieval confidence.
- Add import validation for multilingual FAQ data.

Exit criteria: tests prove retrieval cannot return unapproved or foreign
organization content.

## Phase 4: Language and Answer Policy

- Implement Bangla, English, Banglish, and Sylhet-friendly routing.
- Normalize for retrieval while preserving original transcripts.
- Make confidence thresholds configurable and testable.
- Localize clarification and handoff messages.
- Enforce verified answer mode across all organization-specific answers.

Exit criteria: multilingual fixtures cover successful answers, ambiguity,
unsupported questions, and safe fallback.

## Phase 5: Voice, Calls, and Handoff

- Verify telephony signatures and trusted number-to-tenant routing.
- Build provider adapters and an idempotent voice orchestrator.
- Persist calls, turns, retrieval evidence, errors, and usage.
- Log unknown questions and create human handoff records.
- Extract leads only with explicit tenant and call context.

Exit criteria: integration tests exercise the full pipeline from signed
webhook to response, logging, unknown handling, and handoff.

## Phase 6: Dashboard

- Implement authentication and role-aware navigation.
- Add organization, knowledge, calls, leads, unknown-question, and settings
  workflows.
- Keep API access in typed feature modules or `src/lib/api`.
- Never hardcode organization IDs; derive context from the session.
- Add component and end-to-end tenant-isolation tests.

## Phase 7: Production Readiness

- Correct container service configuration and production image builds.
- Add CORS or same-origin proxy policy, rate limits, metrics, alerts, and
  tracing/request IDs.
- Define transcript, recording, and PII retention policies.
- Add backup, restore, migration, incident, and key-rotation runbooks.
- Perform security review, load tests, and recovery testing.

## Definition of Done

A feature is complete when it has:

- explicit tenant ownership and authorization behavior;
- typed request and response contracts;
- service-layer implementation;
- migration and rollback considerations when storage changes;
- positive, negative, and cross-tenant tests;
- safe low-confidence behavior for knowledge answers;
- logs and metrics appropriate to its operational risk; and
- documentation updated to reflect actual behavior.

