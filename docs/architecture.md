# Architecture

## Current State

Talkque is currently an early monorepo scaffold. FastAPI and Next.js entry
points, service folders, draft schemas, sample data, and container definitions
exist. Database models, tenant authentication, knowledge retrieval, complete
voice orchestration, and most dashboard behavior are still placeholders.

This document describes the intended architecture. A feature is not considered
implemented merely because its folder or interface appears in the repository.

## System Context

```text
Caller
  -> telephony provider
  -> FastAPI voice webhook
  -> voice orchestrator
  -> language and knowledge services
  -> answer policy
  -> telephony response or human handoff

Admin user
  -> Next.js dashboard
  -> authenticated FastAPI API
  -> tenant-scoped PostgreSQL and supporting services
```

PostgreSQL is the system of record. The planned pgvector extension supports
semantic knowledge retrieval. Redis is reserved for short-lived state,
idempotency, caching, queues, or rate limits; it must not become the only copy
of durable business data.

## Voice Pipeline

1. **Phone call:** A telephony provider receives the call and invokes a
   provider-specific webhook.
2. **STT or input:** Audio is transcribed by the provider or an STT service.
   Provider signatures and event identifiers must be validated first.
3. **Language router:** The input is classified and normalized as Bangla,
   English, Banglish, or Sylhet-friendly speech while preserving the original
   transcript.
4. **Retrieval or intent:** Informational questions search only approved
   knowledge owned by the resolved organization. Operational intents can
   capture a lead, request clarification, or initiate handoff.
5. **Answer policy:** The policy checks tenant ownership, approval state,
   source evidence, and confidence. Unsupported answers are blocked.
6. **Response and TTS:** A short response is produced in the caller's language,
   escaped for the provider format, and spoken through TTS. Low-confidence
   responses offer a human handoff.
7. **Logs:** The system records call metadata, turns, retrieval sources,
   confidence, unknown questions, leads, handoffs, errors, and usage under the
   same organization boundary.

## Verified Answer Mode

Verified answer mode is the default for organization-specific facts.

An answer may be returned only when:

- the request has a trusted organization context;
- retrieved knowledge belongs to that organization;
- the knowledge is approved and active;
- the evidence directly supports the proposed answer; and
- confidence meets the configured policy threshold.

When any check fails, the agent must not improvise. It should ask a focused
clarifying question when useful, otherwise log an unknown question and offer
human handoff. Logs should retain source identifiers and policy outcomes for
auditability without exposing one tenant's content to another.

## Tenant Isolation

Tenant context must come from a trusted source such as an authenticated
membership or a verified phone-number/webhook mapping. A client-supplied
organization ID is never sufficient authorization.

All organization-owned tables must include a non-null `organization_id` with
foreign keys, indexes, and appropriate uniqueness constraints. API, service,
repository, background-job, cache, vector-search, log, and file-storage paths
must carry and enforce tenant context. Tests must prove that one organization
cannot read, update, search, or infer another organization's data.

## Language Strategy

- **Bangla:** Preserve Bangla script and use Bangla-aware STT/TTS and
  normalization.
- **English:** Detect genuine English separately instead of treating all Latin
  text as Banglish.
- **Banglish:** Normalize common Latin-script Bangla spellings and variants
  for retrieval while retaining the caller's original phrasing.
- **Sylhet-friendly:** Apply a configurable lexicon and phrasing layer for
  Sylhet usage. Do not assume one spelling or claim full dialect coverage.

Language detection should return a mode and confidence. Low confidence should
fall back to clarification or a configured organization default. Retrieval can
use normalized text, but responses should match the caller's observed language
and remain easy to understand.

## Backend Boundaries

- `app/api`: transport validation, dependencies, status codes, and response
  schemas.
- `app/services`: voice, knowledge, policy, language, lead, handoff, billing,
  and analytics business logic.
- `app/models` and `app/db`: SQLAlchemy persistence and tenant-scoped access.
- `app/schemas`: Pydantic request and response contracts.
- `app/workers`: retryable asynchronous jobs with explicit tenant context.

Route handlers should remain thin. Provider-specific behavior belongs behind
telephony adapters, not throughout the orchestration service.

## Security and Operations

Production readiness requires authentication and role authorization, webhook
signature validation, secret management, XML/output escaping, idempotency,
rate limiting, structured logs, request IDs, metrics, readiness checks,
backups, and tested migrations. Sensitive transcripts and phone numbers need
defined retention and access policies.

