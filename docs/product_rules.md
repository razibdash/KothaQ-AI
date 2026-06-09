# Product Rules

These rules apply to backend, frontend, workers, data imports, prompts,
provider adapters, analytics, and deployment.

## Tenant Isolation

- Every request and background job that handles organization data must have a
  trusted tenant context.
- Resolve tenants from authenticated membership or verified telephony routing,
  never from an untrusted organization ID alone.
- Scope database queries, vector searches, caches, files, logs, and exports to
  one organization.
- Do not hardcode organization IDs in frontend or backend code.
- Add negative tests proving cross-tenant access is denied.

## Verified Answer Mode

- Organization-specific facts must come only from active, approved knowledge
  owned by that organization.
- Retain source identifiers and confidence with the answer decision.
- Do not use draft, disabled, deleted, or foreign-tenant content.
- Do not fill evidence gaps with model memory or plausible guesses.
- If confidence is low, ask a useful clarification or log an unknown question
  and offer human handoff.
- Keep caller-facing responses short, natural, and faithful to the source.

## Language Support

- Support Bangla script, English, Latin-script Banglish, and Sylhet-friendly
  variants.
- Preserve the original caller transcript alongside normalized text.
- Detect English separately from Banglish.
- Use configurable normalization dictionaries and retrieval aliases rather
  than destructively rewriting stored knowledge.
- Return responses in the caller's language when confidence is sufficient.
- When language detection is uncertain, clarify or use the organization's
  configured default without pretending certainty.
- Test spelling, punctuation, code-switching, and dialect variants.

## Unknown Questions and Handoff

- Log unsupported or low-confidence questions with organization, call,
  language, normalized text, confidence, and attempted sources.
- Unknown questions must remain reviewable and must not automatically become
  approved knowledge.
- Human handoff should include caller consent where appropriate, a reason,
  status, destination, and enough context for the representative.
- Failure to reach a human must produce a clear fallback, not a fabricated
  answer.

## Lead Capture

- Capture only fields relevant to the organization's configured workflow.
- Associate leads with the correct organization and originating call.
- Validate and minimize personal data.
- Do not expose lead data across tenants or place sensitive values in logs.

## Voice and Provider Safety

- Verify provider webhook signatures before processing events.
- Make webhook handling idempotent and safe to retry.
- Escape XML and provider-specific output.
- Treat transcripts, phone numbers, recordings, and provider payloads as
  sensitive data.
- Never log provider credentials, signing secrets, raw authorization headers,
  or unrestricted request bodies.

## Engineering Rules

- Use FastAPI controllers for transport concerns and `app/services` for
  business logic.
- Use Pydantic schemas for request and response validation.
- Use SQLAlchemy and Alembic for persistence changes.
- Add or update tests for every backend feature.
- Use Next.js App Router, typed reusable components, and feature/API modules.
- Prefer small, reviewable changes over broad refactors.
- Update documentation when behavior, setup, or operational assumptions change.

## Secrets and Configuration

- Never commit real credentials or API keys.
- Keep local secrets in ignored environment files or an approved secret store.
- Fail startup in non-local environments when required secrets are missing or
  insecure defaults remain.
- Separate development examples from runtime production configuration.

## Minimum Release Gate

A release must not proceed without tenant-isolation tests, verified-answer
fallback tests, signed webhook validation, migration checks, a passing build,
documented rollback steps, and a review of sensitive data handling.
