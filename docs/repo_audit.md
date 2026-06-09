# Repository Audit

Audit date: 2026-06-09

## Scope

This audit covers the repository guidance and the current backend, frontend,
shared, infrastructure, scripts, CI, and documentation folders. It is a
read-only assessment of application code; no application code was changed.

## Executive Summary

The repository is a well-organized early scaffold, not yet a functional or
production-ready SaaS application. The intended boundaries are visible:
FastAPI endpoints, service modules, Pydantic schemas, SQLAlchemy model
locations, a Next.js App Router frontend, shared contracts, and deployment
folders all exist.

The main product guarantees are not implemented yet. In particular, there is
no authentication or tenant resolver, no database session or mapped models,
no tenant-scoped queries, no approved-knowledge retrieval, no unknown-question
logging, and no real handoff flow. The voice webhook returns XML directly from
the route and interpolates an untrusted path value without escaping or
telephony signature validation.

The safest development sequence is to establish a green test/CI baseline,
define tenant ownership in the persistence model, and make tenant resolution
mandatory before implementing knowledge, voice, or dashboard features.

## Repository Map

| Area | Current purpose | Maturity |
| --- | --- | --- |
| `backend/` | FastAPI application, schemas, model placeholders, services, tests, Alembic | Scaffold |
| `frontend/` | Next.js App Router dashboard and typed API client | Scaffold |
| `shared/` | Draft API contract, answer policy, multilingual sample data | Useful design input |
| `infra/` | Backend/frontend Dockerfiles, nginx and Terraform placeholders | Partial scaffold |
| `docs/` | Architecture overview, MVP scope, local runbook | Initial documentation |
| `scripts/` | Bash development launchers | Minimal |
| `.github/` | GitHub Actions workflow | Placeholder only |

## What Is Already Good

- Folder boundaries broadly match the documented FastAPI service/controller
  and Next.js App Router architecture.
- The product intent explicitly includes tenant isolation, approved knowledge,
  low-confidence fallback, human handoff, and multilingual behavior.
- Business capabilities have named service modules rather than being planned
  entirely inside route handlers.
- Pydantic schema and SQLAlchemy/Alembic locations are reserved.
- The shared answer policy correctly says not to guess when knowledge is
  unavailable.
- Sample organization and FAQ data include Bangla, Banglish, Sylhet, and
  English language identifiers.
- The tracked worktree was clean before this audit.

## Prioritized Findings

### Critical

1. **Tenant isolation does not exist yet.**
   There is no authentication, authorization, tenant resolver, request tenant
   context, or database query layer. Collection endpoints have no organization
   scope, and `GET /api/v1/organizations/` is currently an unauthenticated
   global route. Any persistence added behind these endpoints without first
   enforcing tenant context could leak data across organizations.

2. **The voice webhook does not enforce the product safety policy.**
   `backend/app/api/v1/endpoints/voice.py` accepts any organization slug,
   performs no organization lookup, verifies no Twilio/provider signature,
   does not call the voice orchestrator, and does not restrict answers to
   approved organization knowledge.

3. **Untrusted text is interpolated into XML.**
   The organization slug is inserted directly into TwiML/XML. XML-special
   characters can produce malformed output or injection. The telephony adapter
   also interpolates messages without XML escaping.

### High

4. **Persistence is entirely placeholder code.**
   `app/db/session.py`, all model files, and `alembic/env.py` are placeholders.
   There are no migrations. Organizations, branches, knowledge items, calls,
   turns, leads, handoffs, and unknown questions cannot be stored.

5. **A backend module contains a definite syntax error.**
   `app/services/analytics/call_summary.py` has an unterminated string in
   `summarize_call`. The module cannot be imported.

6. **Unknown-question and handoff requirements are not implemented.**
   Low confidence returns a fixed English sentence, but it does not persist an
   unknown question, create a handoff, retain organization context, or support
   the caller's detected language.

7. **Knowledge isolation is only represented by an unused parameter.**
   `search_knowledge(organization_id, query)` always returns an empty result.
   There is no approved/published state, branch scope, source validation, or
   test proving one tenant cannot retrieve another tenant's knowledge.

8. **CI and automated coverage provide no protection.**
   GitHub Actions only prints a placeholder message. The sole backend test
   checks the top-level health endpoint. There are no service, tenant
   isolation, language, webhook, persistence, or frontend tests.

9. **Docker service connection settings are inconsistent.**
   Compose passes `backend/.env.example`, where PostgreSQL and Redis use
   `localhost`. Inside the backend container those hosts refer to the backend
   container, not the `postgres` and `redis` services. This will fail when
   database and Redis connections are enabled.

10. **Browser API calls have no configured cross-origin policy.**
    The frontend defaults to `localhost:3000` and calls the backend at
    `localhost:8000`, but the FastAPI app has no CORS middleware. Browser calls
    will be blocked unless requests are proxied through Next.js or explicit,
    environment-specific CORS origins are configured.

### Medium

11. **Most API routes bypass the intended typed service pattern.**
    Collection routes return raw `list[dict]`, do not declare response models,
    and do not call services. The voice route contains response construction
    that belongs in orchestration/telephony services.

12. **The shared API contract and implemented routes have drifted.**
    The contract lists create/search, voice-turn, and unknown-question
    operations that are absent. Implemented list routes use `"/"`, which also
    means the canonical URLs include trailing slashes while the draft contract
    omits them.

13. **Configuration is not hardened.**
    `SECRET_KEY` defaults to `change-me`, production-required settings are not
    validated, provider settings are not represented in `Settings`, and
    `.env.example` is used as a runtime environment file by Compose.

14. **Language handling is too heuristic for declared support.**
    The ASCII-ratio router classifies ordinary English as Banglish, recognizes
    no explicit English or Sylheti mode, and has no confidence/unknown result.
    Banglish normalization is whitespace-token based, and the Sylhet lexicon
    is not integrated into orchestration. None of this behavior has tests.

15. **The frontend is page-level scaffolding only.**
    Dashboard pages contain headings, login has no authentication flow, route
    groups have no shared dashboard/auth layouts, and the API client is unused.
    There is no mechanism for deriving organization context from the signed-in
    user. No organization ID is hardcoded, which is a good starting property.

16. **Dependency builds are not reproducible.**
    Frontend dependencies use `"latest"` and there is no tracked lockfile.
    The backend uses lower bounds without a lock/constraints workflow. Docker
    separately lists Python dependencies instead of installing the project
    metadata, making local and container environments easier to drift.

17. **Operational readiness is absent.**
    Health checks do not verify dependencies, there is no structured logging,
    request/correlation ID, metrics, error policy, rate limiting, background
    job implementation, deployment configuration, or production nginx setup.

### Low

18. **Health endpoints are duplicated.**
    Both `/health` and `/api/v1/health/` exist with slightly different
    responses and no documented distinction between liveness and readiness.

19. **Local development guidance is Unix-oriented.**
    The runbook and scripts use Bash activation/launch commands despite this
    checkout being on Windows. Platform-specific alternatives would reduce
    setup friction.

20. **Some documentation formatting and naming need cleanup.**
    `AGENTS.md` ends with an unmatched code fence, the root README shows a
    different repository directory name, and the architecture document is a
    conceptual flow rather than a record of current implementation.

## System Assessments

### Backend

The package structure is appropriate, but only health behavior is currently
executable by design. Models, database access, migrations, CRUD operations,
voice orchestration, provider verification, and most service behavior remain
stubs. Before adding feature endpoints, introduce a request-scoped authenticated
actor/tenant context and require organization scope at service/repository
boundaries.

Every model containing organization-owned data should carry a non-null
`organization_id` foreign key and suitable indexes. Branch-owned data should
also be constrained to the parent organization. Service methods should accept
the trusted tenant context rather than a tenant identifier supplied directly
by an untrusted client.

### DB and Storage

PostgreSQL with pgvector and Redis are declared in Compose, but neither is used
by the application. SQLAlchemy models, session management, and Alembic are
placeholders, and there are no migrations or storage tests. Every tenant-owned
record needs a non-null `organization_id`, database constraints and indexes,
and query APIs that require trusted tenant context. Knowledge also needs an
approval state so retrieval cannot use draft or unapproved content.

### Voice Webhook

The incoming-call route returns basic XML, so the route itself is reachable
once the backend runs. It does not validate provider signatures, resolve a
trusted organization, escape XML values, invoke the orchestrator, persist call
turns, enforce verified answers, log unknown questions, capture leads, or
create a handoff. These controls should be implemented and tested together
before exposing the webhook publicly.

### Language

The repository contains an ASCII-ratio language router, a small Banglish term
map, and a Sylhet-friendly lexicon. They are useful prototypes but are not
integrated into the voice flow. English is likely to be misclassified as
Banglish, punctuation and spelling variants are not normalized, and there is
no language confidence or fallback strategy. Tests should be driven by the
sample multilingual questions in `shared/sample-data/`.

### Frontend

The App Router and typed API helper are present, but the dashboard is not
connected to data or authentication. Organization context should come from the
authenticated session and backend authorization, never from a hardcoded ID or
an unrestricted client-controlled selector. API error handling should account
for authentication, authorization, validation, and request correlation.

### Shared

The answer policy and sample multilingual data are useful acceptance-test
inputs. The API contract should become versioned and testable once endpoint
schemas stabilize. It currently describes future behavior rather than the
implemented API and does not define authentication, tenant context, request
bodies, responses, errors, pagination, or idempotency.

### Tests

There is one backend test for `GET /health`. No tests cover services,
persistence, tenant isolation, API authorization, voice provider validation,
language behavior, verified-answer fallback, unknown-question logging, lead
capture, handoff, or frontend behavior. CI currently executes no tests.

### Deployment

The Compose topology is sensible for local development, but service hostnames,
health checks, startup/migration behavior, and secret handling need work.
Docker builds should use lockable project dependencies. Nginx and Terraform are
placeholders and should not be treated as deployable production configuration.

### Security

Authentication, authorization, organization membership, role checks, tenant
resolution, provider webhook verification, rate limiting, and audit logging
are absent. `SECRET_KEY` has an unsafe default, browser CORS/proxy behavior is
undefined, and generated XML is not escaped. The highest production risk is
adding persistence or public webhooks before tenant and trust boundaries are
mandatory at API, service, and database layers.

### Documentation

The MVP priorities align with `AGENTS.md`, but the docs do not yet define the
tenant threat model, data ownership rules, knowledge approval lifecycle,
confidence policy, unknown-question lifecycle, handoff states, or multilingual
acceptance criteria. Those decisions should be documented alongside the first
persistence and service implementations.

## Current Test and Build Results

| Check or test | Command | Result |
| --- | --- | --- |
| Tracked worktree baseline | `git status --short` | Passed at initial audit; clean |
| Backend health test | `python -m pytest -q` from `backend/` | Not executed: `python` is unavailable |
| Backend health test, launcher fallback | `py -3 -m pytest -q` from `backend/` | Not executed: `py` is unavailable |
| Backend syntax compilation | `python -m compileall -q app` | Not executed: Python is unavailable |
| Frontend production build | `npm run build` from `frontend/` | Failed to start: dependencies are not installed and `next` is unavailable |
| Markdown whitespace validation | `git diff --check` | Passed |

Because Python could not be executed, the existing health test was not
validated during this audit, so no backend test can currently be reported as
passing or failing. The syntax defect in `call_summary.py` was found by direct
source inspection and would fail import/compilation when Python is available.

## Recommended Next 10 Tasks

1. **Restore a green development baseline.** Fix the syntax defect, install
   pinned backend/frontend dependencies, add lockfiles or constraints, and
   document commands that work on Windows and Unix.
2. **Make CI enforce quality.** Run backend compilation, lint/type checks and
   pytest, plus frontend type checking/build, instead of the placeholder echo.
3. **Define authentication and trusted tenant context.** Model authenticated
   actors, organization membership, and roles; reject requests without valid
   tenant context.
4. **Implement tenant-safe persistence.** Add SQLAlchemy session/base,
   Organization and Branch models, Alembic migration, constraints, indexes,
   and cross-tenant denial tests.
5. **Implement approved knowledge management.** Add tenant-scoped knowledge
   CRUD, approval/publish states, source metadata, and tests that exclude
   unapproved or foreign-tenant content.
6. **Implement multilingual routing and normalization.** Distinguish Bangla,
   English, Banglish, and Sylhet-friendly inputs with confidence/fallback and
   fixture-driven tests.
7. **Build verified knowledge search and answer policy.** Return source and
   confidence, prohibit unsupported answers, and localize low-confidence
   responses.
8. **Implement the unknown-question and handoff lifecycle.** Persist unknowns
   with tenant/call context, support review and approval, and create trackable
   human handoff records.
9. **Harden and connect the voice webhook.** Verify provider signatures,
   resolve tenants through trusted routing, escape XML, ensure idempotency,
   invoke orchestration, and persist calls/turns, leads, and usage.
10. **Connect and operationalize the dashboard.** Add authenticated,
    role-aware feature pages and API modules, then correct Compose hostnames,
    configure CORS/proxy behavior, health/readiness checks, logs, metrics,
    rate limits, backups, and deployment runbooks.

## Definition of Ready for Feature Work

Feature development should begin only when the affected path has:

- a trusted tenant context and explicit ownership rule;
- typed request/response schemas;
- service-layer business logic;
- persistence migration when data changes;
- positive, negative, and cross-tenant tests;
- unknown-answer/handoff behavior where knowledge confidence is involved; and
- CI execution of the relevant checks.

The immediate next task is item 1. Business CRUD should not begin until items
1 through 4 establish executable tests and a mandatory tenant boundary.
