# Codex Prompt Playbook: Multilingual SaaS Voice Agent

**Project:** Bangla-English-Sylhet-friendly SaaS voice agent for schools, universities, and service companies  
**Goal:** Use Codex phase by phase to build a production-ready MVP without wasting time on vague tasks.

---

## 0. How to use this document

Use this playbook like a development operating manual.

1. Create or open your repo.
2. Add the `AGENTS.md` from section 2 at the repo root.
3. Run Codex phase by phase.
4. Do not paste multiple phases at once.
5. After each phase, ask Codex to run tests, show diff summary, and list what is incomplete.
6. Commit only when acceptance criteria pass.

**Golden rule:** one Codex task = one bounded feature or fix.

---

## 1. Product context for every Codex task

Paste this context at the top of large tasks if Codex does not already know the product.

```text
We are building a SaaS multilingual AI voice agent for schools, universities, coaching centers, diagnostic centers, consultancies, and service companies.

Core use case:
When people call an institution, the AI voice agent answers common questions such as admission fee, CSE cost, scholarship, office hours, location, documents, appointments, service price, and support hours. The system must handle many simultaneous calls and transfer to a human when needed.

Target markets:
1. Bangladesh, especially Bangla, Banglish, and Sylhet-friendly support.
2. International market with English and future multilingual support.

Core product principles:
- Multi-tenant SaaS: each organization has separate data, settings, phone numbers, branches, knowledge base, and call logs.
- Verified answer mode: do not invent fees, deadlines, legal/payment rules, or policy answers. Answer only from approved knowledge base or transfer/escalate.
- Language support: Bangla, English, Banglish, and Sylhet-friendly normalization.
- Human handoff: transfer when caller asks for human, confidence is low, caller is angry, or topic is sensitive.
- Learning loop: unknown questions are logged so admins can approve answers and improve the knowledge base.
- Lead capture: collect caller name, phone, program/service interest, branch, and callback time when useful.

Current preferred stack:
- Backend: FastAPI, Python 3.11+
- DB: PostgreSQL, SQLAlchemy or SQLModel, Alembic migrations
- Vector search: pgvector or a clean abstraction that can later use pgvector
- Queue/cache: Redis + RQ/Celery later
- Voice webhook MVP: Twilio-compatible TwiML endpoints
- Dashboard later: Next.js + Tailwind
- Testing: pytest
- Deployment: Docker, docker-compose, later CI/CD
```

---

## 2. Root `AGENTS.md` for the repository

Create a file named `AGENTS.md` in the repo root and paste this:

```markdown
# AGENTS.md

## Project

We are building a SaaS multilingual AI voice agent for schools, universities, coaching centers, diagnostic centers, consultancies, and service companies.

The system answers phone calls using approved organization knowledge bases, captures leads, logs unknown questions, and transfers to humans when needed. It must support Bangla, English, Banglish, and Sylhet-friendly normalization.

## Non-negotiable product rules

1. Never invent organization-specific facts such as fees, deadlines, waiver rules, admission requirements, payment instructions, legal terms, or medical/service claims.
2. If confidence is low or the answer is not in the approved knowledge base, log an unknown question and offer human handoff.
3. Always preserve tenant isolation. Never leak one organization's data to another organization.
4. Every feature must include tests or a clear reason tests are not applicable.
5. Prefer simple, maintainable architecture over clever abstractions.
6. Keep user-facing voice responses short, polite, and easy to understand over a phone call.
7. Code must be production-minded: typed, validated, logged, and documented where necessary.
8. No secrets in code, tests, logs, fixtures, or documentation.

## Architecture preferences

- Backend: FastAPI.
- Database: PostgreSQL-compatible models using SQLAlchemy/SQLModel.
- Migrations: Alembic.
- Testing: pytest.
- API style: clear REST endpoints with Pydantic request/response models.
- Voice: start with Twilio-compatible webhook/TwiML; keep provider abstraction so LiveKit/SIP/OpenAI Realtime can be added later.
- AI pipeline: STT -> language router -> intent/retrieval -> answer policy -> TTS/voice response -> logs.

## Coding standards

- Use small functions with clear names.
- Add type hints for public functions.
- Validate tenant/org IDs on every tenant-scoped operation.
- Keep business logic outside route handlers where possible.
- Add tests for success, failure, and tenant isolation paths.
- For migrations, include both model changes and Alembic revision.
- Do not introduce large dependencies without explaining why.

## Before coding

For any non-trivial task:
1. Inspect the relevant files.
2. Write a short implementation plan.
3. Mention risks or assumptions.
4. Then implement.

## After coding

Always provide:
1. Summary of changes.
2. Files changed.
3. Tests run and results.
4. Any remaining TODOs.
5. Suggested next task.

## Testing commands

Prefer these commands when applicable:

```bash
pytest -q
python -m pytest -q
ruff check .
ruff format --check .
mypy .
```

If any command is unavailable, explain that instead of pretending it passed.
```

---

## 3. Codex task style guide

Use this structure for every task:

```text
Context:
[Short product + current repo context]

Task:
[One clear task]

Requirements:
- Requirement 1
- Requirement 2
- Requirement 3

Acceptance criteria:
- Criteria 1
- Criteria 2
- Criteria 3

Constraints:
- Do not break existing tests.
- Do not add secrets.
- Keep tenant isolation.

Before coding:
- Inspect relevant files.
- Propose a short plan.

After coding:
- Run tests.
- Summarize changed files.
- List remaining risks.
```

---

## 4. Phase 0 — Repo audit and development baseline

### Prompt 0.1 — Audit existing repo

```text
Context:
We are building a SaaS multilingual AI voice agent for schools, universities, and service companies. The product must support multi-tenant organizations, Bangla/English/Banglish/Sylhet-friendly language handling, verified answers, unknown question logging, lead capture, and human handoff.

Task:
Audit the current repository and create a development baseline.

Requirements:
- Inspect project structure, dependencies, routes, services, tests, config, and data files.
- Identify what already works and what is missing.
- Identify architecture risks for turning this into a production SaaS.
- Do not modify code yet unless a tiny documentation file is needed.

Deliverables:
- A concise repo audit report in `docs/repo_audit.md`.
- A recommended next 10 development tasks in priority order.
- A list of tests that currently pass/fail and commands used.

Acceptance criteria:
- `docs/repo_audit.md` exists.
- The report includes backend, DB/storage, voice webhook, language, tests, deployment, and security sections.
- No product code is changed.
```

### Prompt 0.2 — Add project docs skeleton

```text
Task:
Add a clean documentation skeleton for this SaaS voice agent project.

Requirements:
Create or update:
- `README.md`
- `docs/architecture.md`
- `docs/development_plan.md`
- `docs/local_setup.md`
- `docs/product_rules.md`

Content requirements:
- Explain the voice pipeline: phone call -> STT/input -> language router -> retrieval/intent -> answer policy -> response/TTS -> logs.
- Explain verified answer mode.
- Explain tenant isolation.
- Explain Bangla, English, Banglish, and Sylhet-friendly support strategy.
- Include local setup commands.

Acceptance criteria:
- New docs are clear enough for a new developer to start.
- No fake API keys or secrets.
- Existing tests still pass.
```

---

## 5. Phase 1 — Configuration and environment hardening

### Prompt 1.1 — Typed settings

```text
Task:
Implement typed application settings.

Requirements:
- Add a central settings module using Pydantic settings or the existing project convention.
- Support environment variables for:
  - app environment
  - database URL
  - public base URL
  - default tenant/org ID for demo
  - human handoff fallback number
  - OpenAI API key, optional
  - Twilio auth token, optional
  - STT provider, optional
  - TTS provider, optional
- Add `.env.example` with safe placeholder values.
- Ensure the app starts without paid provider keys by using mock/local modes.

Acceptance criteria:
- Settings are imported from one place.
- App runs locally with `.env.example` copied to `.env`.
- Tests cover default settings behavior.
```

### Prompt 1.2 — Structured logging

```text
Task:
Add structured logging for voice calls and backend operations.

Requirements:
- Create a logging utility or configure Python logging cleanly.
- Log call lifecycle events: incoming call, user input received, language detected, answer selected, unknown question, handoff, error.
- Never log secrets.
- Avoid logging full sensitive caller data unless necessary; mask phone numbers where appropriate.

Acceptance criteria:
- Logs include tenant/org ID and call/session ID when available.
- Error paths are logged with enough context to debug.
- Tests do not fail due to logging changes.
```

---

## 6. Phase 2 — Database foundation

### Prompt 2.1 — PostgreSQL models and migrations

```text
Task:
Replace or prepare the current storage layer with production-ready database models for multi-tenant SaaS.

Requirements:
Implement models and Alembic migrations for:
- organizations
- branches
- phone_numbers
- knowledge_items or faqs
- conversations
- call_turns
- unknown_questions
- leads
- handoffs

Important fields:
organizations:
- id, slug, name, default_language, supported_languages, timezone, created_at, updated_at

branches:
- id, organization_id, slug, name, city, region, country, address, phone, timezone

knowledge_items/faqs:
- id, organization_id, branch_id nullable, question, answer, language, tags, status, source_type, source_reference, created_at, updated_at

conversations:
- id, organization_id, branch_id nullable, provider, provider_call_id, caller_phone_masked, detected_language, status, started_at, ended_at

call_turns:
- id, conversation_id, role, input_text, normalized_text, output_text, confidence, intent, created_at

unknown_questions:
- id, organization_id, conversation_id nullable, question_text, normalized_text, detected_language, status, suggested_answer nullable, created_at

leads:
- id, organization_id, conversation_id nullable, name, phone_masked, interest, branch_id nullable, callback_time nullable, status, created_at

handoffs:
- id, organization_id, conversation_id, reason, target_number_masked, status, created_at

Acceptance criteria:
- Migration creates all required tables.
- Models include tenant relationships.
- Tests cover creating an organization, branch, FAQ, conversation, unknown question, and lead.
- No tenant-scoped query should be possible without organization context in service functions.
```

### Prompt 2.2 — Seed demo tenants

```text
Task:
Create seed data for demo tenants.

Requirements:
Add a seed script that creates:
1. Demo University Sylhet
2. Demo School Sylhet
3. Demo Service Company

Each tenant should include:
- default language settings
- at least one branch
- 20 approved FAQs
- handoff settings

FAQ topics:
- CSE cost/admission fee
- admission documents
- scholarship/waiver
- office hours
- location
- contact/callback
- program list
- application deadline placeholder
- payment method placeholder with safe wording

Acceptance criteria:
- Seed script is idempotent.
- Running it twice does not duplicate rows.
- README documents how to run it.
```

---

## 7. Phase 3 — Tenant-safe service layer

### Prompt 3.1 — Organization resolver

```text
Task:
Implement organization resolution for voice and API requests.

Requirements:
- Resolve organization by slug in routes like `/voice/incoming/{org_slug}`.
- Optionally resolve by incoming phone number later.
- Return a clear 404/error for unknown org.
- Store organization context in request/service layer.

Acceptance criteria:
- Voice routes use organization slug and never use global demo data accidentally.
- Tests cover valid org, invalid org, and tenant isolation.
```

### Prompt 3.2 — Tenant-scoped knowledge service

```text
Task:
Implement a tenant-scoped knowledge service.

Requirements:
- Add functions to search approved knowledge items by organization and optional branch.
- Filter by status=`approved` only for caller-facing answers.
- Add basic keyword/fuzzy search first if vector search is not ready.
- Return confidence score and source item ID.
- Never return items from another organization.

Acceptance criteria:
- Tests prove organization A cannot retrieve organization B knowledge.
- Low-confidence queries return no verified answer.
- Search supports Bangla, English, and Banglish-like queries at basic level.
```

---

## 8. Phase 4 — Language router: Bangla, English, Banglish, Sylhet-friendly

### Prompt 4.1 — Language detection and normalization

```text
Task:
Build a language router service for Bangla, English, Banglish, and Sylhet-friendly caller text.

Requirements:
Create `language_router` with:
- `detect_language(text) -> detected language code`
- `normalize_text(text, language_code) -> normalized searchable text`
- `choose_response_language(caller_text, org_default, supported_languages) -> language code`

Supported language codes:
- `bn-BD` for Bangla script
- `bn-Latn` for Banglish romanized Bangla
- `syl-BD` for Sylhet-friendly mode
- `en-US` or `en-GB` for English

Normalization examples:
- `cse cost koto` -> `cse cost কত / cse tuition fee`
- `admission er jonno ki ki lagbe` -> `admission documents requirements`
- `office koytay bondho` -> `office hours closing time`
- Sylhet-friendly terms should map common words without pretending perfect Sylheti ASR.

Acceptance criteria:
- Unit tests for Bangla script, English, Banglish, mixed Banglish-English, and Sylhet-friendly phrases.
- Function is deterministic and does not call paid APIs.
- Normalizer improves knowledge search tests.
```

### Prompt 4.2 — Sylhet-friendly lexicon

```text
Task:
Add a small Sylhet-friendly lexicon module for search normalization.

Requirements:
- Create a maintainable dictionary/list for common Sylhet/Sylhet-style caller expressions.
- Map them to standard searchable concepts.
- Include examples for fees, office time, location, admission, documents, scholarship, human/operator, callback, and branch.
- Add comments that this is a practical normalization layer, not a full Sylheti language model.

Acceptance criteria:
- Tests show at least 20 Sylhet-friendly/Banglish phrases normalize to useful search terms.
- The lexicon is easy to extend by non-expert developers.
```

### Prompt 4.3 — Response style engine

```text
Task:
Create a response style engine for voice replies.

Requirements:
- Generate short phone-friendly replies in Bangla, Banglish, or English depending on selected response language.
- Keep replies under roughly 2-3 short sentences unless the caller asks for details.
- Add style modes:
  - formal_parent
  - student_friendly
  - corporate_formal
  - international_english
- Do not change factual content from the verified answer.

Acceptance criteria:
- Tests show facts are preserved.
- Voice replies are shorter than raw FAQ answers when needed.
- Unknown answer fallback is available in each supported style/language.
```

---

## 9. Phase 5 — Verified answer policy and unknown-question loop

### Prompt 5.1 — Answer policy service

```text
Task:
Implement a verified answer policy service.

Requirements:
Input:
- caller text
- normalized text
- organization ID
- branch ID optional
- candidate knowledge item with confidence

Output:
- answer_allowed boolean
- response_text
- confidence
- reason
- source_knowledge_item_id nullable
- should_handoff boolean
- should_log_unknown boolean

Rules:
- If confidence is high and source is approved, answer.
- If confidence is medium, answer with cautious wording only if the answer is not sensitive.
- If confidence is low, log unknown and offer human handoff.
- Sensitive topics such as exact fees, deadline, payment, legal/medical claims must require approved source.
- Never invent missing details.

Acceptance criteria:
- Tests cover high confidence, low confidence, cross-tenant, sensitive topic, and unknown question.
```

### Prompt 5.2 — Unknown question workflow

```text
Task:
Build the unknown question logging and approval workflow in the backend.

Requirements:
- When answer policy says unknown, create `unknown_questions` record.
- Add admin API endpoints:
  - list unknown questions by org
  - mark as ignored
  - add approved answer, which creates/updates a knowledge item
- Ensure only organization-scoped data is returned.

Acceptance criteria:
- Tests cover unknown question creation and approval into KB.
- Approved unknown answer becomes searchable for future calls.
- No cross-tenant leakage.
```

---

## 10. Phase 6 — Voice webhook MVP

### Prompt 6.1 — Twilio-compatible incoming call flow

```text
Task:
Implement or improve Twilio-compatible voice webhook endpoints.

Requirements:
Routes:
- `POST /voice/incoming/{org_slug}`
- `POST /voice/gather/{org_slug}`
- `POST /voice/handoff/{org_slug}` optional

Call flow:
1. Incoming call greets caller based on organization language settings.
2. Gather speech and/or keypad input.
3. Process caller text through language router, knowledge search, answer policy.
4. Reply with short voice-friendly response.
5. Ask if caller has another question.
6. Transfer to human if requested or policy requires handoff.

Acceptance criteria:
- Returns valid XML/TwiML-style responses.
- Handles empty speech result gracefully.
- Logs conversation and call turns.
- Tests cover incoming, answer found, answer unknown, human handoff, and invalid org.
```

### Prompt 6.2 — Provider abstraction

```text
Task:
Create a voice provider abstraction so Twilio is not hardcoded everywhere.

Requirements:
- Define an interface/service for voice responses: say, gather, redirect, dial/handoff, hangup.
- Implement Twilio-compatible XML adapter.
- Keep route handlers thin.
- Prepare for future LiveKit/SIP/OpenAI Realtime adapters without implementing them now.

Acceptance criteria:
- Voice routes call the provider abstraction.
- Existing Twilio-compatible behavior remains working.
- Tests cover adapter output.
```

### Prompt 6.3 — Call state and repeat question handling

```text
Task:
Add call state handling for multi-turn calls.

Requirements:
- Track conversation by provider call ID.
- Store each user utterance and agent response as call turns.
- Allow caller to ask multiple questions in the same call.
- Detect exit phrases like goodbye, thank you, ar lagbe na, no thanks.
- Detect human request phrases like operator, human, admission officer, মানুষ, অফিসে কথা বলবো.

Acceptance criteria:
- Tests cover multi-turn conversation.
- Exit phrases end call politely.
- Human phrases trigger handoff.
```

---

## 11. Phase 7 — Lead capture engine

### Prompt 7.1 — Lead capture rules

```text
Task:
Implement a lead capture engine for admission/service inquiries.

Requirements:
- Detect lead-worthy intents: admission, apply, visit, callback, price, demo, appointment.
- Ask at most one lead question per call turn.
- Capture:
  - name
  - phone masked or provider caller ID masked
  - interest/program/service
  - branch/city
  - preferred callback time
- Do not make the call feel like a long form.

Acceptance criteria:
- Tests cover lead intent detection and incremental lead capture.
- Lead is linked to organization and conversation.
- Agent can answer FAQ and capture lead in the same call.
```

### Prompt 7.2 — Lead summary

```text
Task:
Generate call and lead summaries after conversations.

Requirements:
- Create a summary service that summarizes call outcome:
  - answered questions
  - unknown questions
  - lead interest
  - handoff reason
  - follow-up needed
- Store summary on conversation or related table.
- Do not require LLM for MVP; use deterministic summary first.

Acceptance criteria:
- Conversation summary exists after call end or can be generated on demand.
- Tests cover answered, unknown, handoff, and lead scenarios.
```

---

## 12. Phase 8 — Admin API

### Prompt 8.1 — Admin organization and FAQ API

```text
Task:
Build admin REST API endpoints for organizations, branches, and knowledge items.

Requirements:
Endpoints should support:
- list/get organization by slug
- list/create/update branches
- list/create/update/archive knowledge items
- approve/draft status for knowledge items

Security placeholder:
- If full auth is not implemented yet, add a clear dependency placeholder and document that it must be replaced before production.
- Still enforce organization scoping in routes.

Acceptance criteria:
- Tests cover CRUD and tenant isolation.
- API schemas are documented by FastAPI OpenAPI.
```

### Prompt 8.2 — CSV FAQ import

```text
Task:
Add CSV import for knowledge base items.

Requirements:
- Accept CSV with columns: question, answer, language, branch_slug optional, tags optional, status optional, source_reference optional.
- Validate required fields.
- Report row-level errors.
- Do not import invalid rows silently.
- Default status should be draft unless explicitly approved.

Acceptance criteria:
- Tests cover valid import, invalid rows, duplicate handling, and tenant isolation.
- Documentation includes CSV example.
```

---

## 13. Phase 9 — RAG/vector search upgrade

### Prompt 9.1 — Search abstraction

```text
Task:
Refactor knowledge search into a clean search abstraction.

Requirements:
- Create a search interface with at least:
  - keyword search implementation
  - placeholder/vector implementation interface
- Keep existing keyword search working.
- Prepare for pgvector embeddings but do not require paid APIs in tests.

Acceptance criteria:
- Tests pass with keyword search.
- Service layer does not care which search backend is used.
```

### Prompt 9.2 — pgvector-ready embedding storage

```text
Task:
Add pgvector-ready fields and embedding workflow behind a feature flag.

Requirements:
- Add embedding column or separate table if pgvector is available.
- Add a deterministic fake embedding provider for tests.
- Add an embedding job/service that updates embeddings for approved knowledge items.
- Do not call external APIs in tests.

Acceptance criteria:
- Tests run without external API keys.
- Search can use fake vector similarity in tests or fallback safely.
- Documentation explains how to enable real embeddings later.
```

---

## 14. Phase 10 — STT/TTS provider abstraction

### Prompt 10.1 — STT abstraction

```text
Task:
Create a speech-to-text provider abstraction.

Requirements:
- Define STT provider interface.
- Add mock provider for tests/local development.
- Add placeholder provider classes for future Google/OpenAI/Azure without hardcoding credentials.
- Language hints should support bn-BD, en-US, and mixed Banglish use cases.

Acceptance criteria:
- Existing voice flow can still use text from Twilio SpeechResult.
- Unit tests cover mock STT behavior.
- Docs explain where real STT provider integration should be added.
```

### Prompt 10.2 — TTS abstraction and audio cache

```text
Task:
Create a text-to-speech provider abstraction and optional audio cache design.

Requirements:
- Define TTS provider interface.
- Add mock provider that returns text or fake audio path for tests.
- Add provider setting per organization/language.
- Add cache key design for repeated FAQ answers.
- Do not require real TTS provider in MVP tests.

Acceptance criteria:
- Voice response generation can remain XML text-based for Twilio MVP.
- TTS abstraction is ready for future audio streaming or cached MP3 files.
- Tests cover provider selection by language.
```

---

## 15. Phase 11 — Dashboard frontend

### Prompt 11.1 — Next.js dashboard skeleton

```text
Task:
Create a Next.js + Tailwind dashboard skeleton for the SaaS voice agent admin panel.

Requirements:
Pages:
- login placeholder
- organization overview
- call logs
- unknown questions
- knowledge base
- leads
- settings/language/voice

Important UX:
- Show unknown questions prominently.
- Allow admin to approve an unknown question into the knowledge base.
- Show call outcome metrics: answered, transferred, unknown, leads.

Acceptance criteria:
- Dashboard runs locally.
- API client is organized.
- Empty states are included.
- No real auth claim if auth is only placeholder.
```

### Prompt 11.2 — Unknown question approval UI

```text
Task:
Build the unknown question approval UI.

Requirements:
- List unknown questions by organization.
- Show caller question, normalized text, detected language, conversation date, and status.
- Admin can write/edit an answer and approve it into KB.
- Admin can ignore irrelevant questions.

Acceptance criteria:
- UI calls backend endpoints correctly.
- Optimistic or clear loading states.
- Error states are visible.
```

---

## 16. Phase 12 — Security, auth, and production readiness

### Prompt 12.1 — Auth and tenant access model

```text
Task:
Design and implement the first version of admin authentication and tenant authorization.

Requirements:
- Add user/admin model if not present.
- Users belong to organizations with roles: owner, admin, viewer.
- Protect admin API routes.
- Ensure a user cannot access another organization's data.
- Use a simple secure approach appropriate for MVP; document production improvements.

Acceptance criteria:
- Tests cover authorized access, unauthorized access, cross-tenant denial, and role limitations.
- No hardcoded passwords or secrets.
```

### Prompt 12.2 — Rate limits and webhook verification

```text
Task:
Add production security protections for public voice webhooks and admin APIs.

Requirements:
- Add rate limiting or a clear abstraction for it.
- Add Twilio signature verification or provider webhook verification abstraction.
- Add request size limits where appropriate.
- Add secure error responses that do not leak internals.

Acceptance criteria:
- Tests cover invalid webhook signature when verification is enabled.
- Local development can disable verification with explicit env setting.
- Security behavior is documented.
```

### Prompt 12.3 — Docker and CI

```text
Task:
Make the project easy to run and test in Docker and CI.

Requirements:
- Dockerfile for backend.
- docker-compose for backend, PostgreSQL, Redis if used.
- Healthcheck endpoint.
- GitHub Actions or CI workflow for lint/test if repo uses GitHub.
- Update README.

Acceptance criteria:
- `docker compose up` works for local development.
- Test command is documented.
- CI runs tests without paid provider keys.
```

---

## 17. Code review prompts

### Prompt — Review current branch before merge

```text
Task:
Review the current branch as a senior backend engineer before merge.

Focus areas:
- Tenant isolation
- Verified answer policy
- Security and secret handling
- Test coverage
- Database migration safety
- Voice webhook correctness
- Language router correctness
- Error handling and logging
- Simplicity and maintainability

Deliverables:
- List blocking issues first.
- Then non-blocking improvements.
- Then suggested tests to add.
- Do not make code changes unless I explicitly ask.
```

### Prompt — Fix review issues

```text
Task:
Fix the blocking issues from the previous code review.

Requirements:
- Only fix blocking issues unless a non-blocking fix is tiny and safe.
- Add or update tests for each fix.
- Keep changes minimal.

Acceptance criteria:
- Tests pass.
- Summary maps each fix to the review issue.
```

---

## 18. Bug-fix prompt templates

### Prompt — Reproduce and fix bug

```text
Context:
This is a SaaS multilingual voice agent. Tenant isolation and verified answers are critical.

Bug:
[PASTE BUG DESCRIPTION]

Observed behavior:
[WHAT HAPPENS]

Expected behavior:
[WHAT SHOULD HAPPEN]

Task:
Reproduce the bug with a failing test first, then fix it.

Requirements:
- Inspect relevant code.
- Add a regression test that fails before the fix.
- Implement the smallest safe fix.
- Run the relevant tests.

Acceptance criteria:
- Regression test passes.
- Existing tests pass.
- Explain root cause briefly.
```

---

## 19. Refactor prompt templates

### Prompt — Refactor safely

```text
Task:
Refactor [MODULE/AREA] for maintainability without changing behavior.

Requirements:
- Keep public behavior the same.
- Add tests first if coverage is missing.
- Make small commits/changes.
- Do not introduce new dependencies unless necessary.
- Do not change database schema unless explicitly needed.

Acceptance criteria:
- Existing tests pass.
- New tests cover extracted logic.
- Provide before/after explanation.
```

---

## 20. Product-specific high-value feature prompts

### Prompt — Branch-aware answers

```text
Task:
Implement branch-aware answer selection.

Requirements:
- Detect branch/city from caller text when possible, e.g. Sylhet campus, Dhaka campus.
- Prefer branch-specific FAQ if branch is detected.
- Fall back to organization-level FAQ if no branch-specific answer exists.
- If multiple branches match ambiguously, ask a clarification question.

Acceptance criteria:
- Tests cover Sylhet branch, Dhaka branch, no branch, ambiguous branch, and fallback.
- Tenant isolation remains enforced.
```

### Prompt — Human handoff rules

```text
Task:
Implement configurable human handoff rules per organization.

Requirements:
Handoff should trigger when:
- caller asks for human/operator/admission officer
- answer confidence is low
- sensitive topic is not verified
- caller sentiment/phrase indicates anger or urgency
- office policy requires handoff for specific intents

Organization settings should define:
- handoff phone number
- business hours
- fallback message outside business hours
- handoff keywords

Acceptance criteria:
- Tests cover each handoff trigger.
- Handoff records are stored with reason.
- No unmasked phone number is stored in logs unless explicitly required.
```

### Prompt — Admission lead mode

```text
Task:
Implement admission lead mode for education tenants.

Requirements:
- When caller asks about admission, program, fee, scholarship, or documents, capture interest.
- Ask only one follow-up question at a time.
- Support Bangla, Banglish, and English phrasing.
- Do not block answering the caller's original question.

Example:
Caller: CSE cost koto?
Agent: CSE program-er fee information holo [verified answer]. Apni ki Sylhet campus-e admission nite interested?

Acceptance criteria:
- Tests cover lead capture after FAQ answer.
- Lead data is linked to conversation and organization.
```

### Prompt — Missed-question learning loop

```text
Task:
Build the missed-question learning loop end to end.

Requirements:
- Unknown caller questions are logged automatically.
- Admin can approve an answer.
- Approved answer becomes a knowledge item.
- Future calls with similar question use the new approved answer.

Acceptance criteria:
- End-to-end test covers unknown -> approve -> future answer found.
- Dashboard/API clearly marks pending unknown questions.
```

---

## 21. Testing prompts

### Prompt — Add tests for critical flows

```text
Task:
Add comprehensive tests for the most critical SaaS voice-agent flows.

Test areas:
- Tenant isolation
- Incoming call flow
- Answer found from approved KB
- Low confidence unknown question
- Human handoff
- Lead capture
- Language detection and normalization
- Branch-aware answer selection
- Unknown question approval

Acceptance criteria:
- Tests are deterministic.
- No external API calls.
- Test data includes Bangla, English, Banglish, and Sylhet-friendly phrases.
```

### Prompt — Performance smoke test

```text
Task:
Add a lightweight performance/concurrency smoke test for voice request handling.

Requirements:
- Simulate multiple concurrent voice gather requests.
- Ensure tenant-scoped responses are correct.
- Do not require real telephony provider.
- Keep test lightweight enough for CI.

Acceptance criteria:
- Test catches obvious shared-state bugs.
- Test runs reliably in CI.
```

---

## 22. Deployment prompts

### Prompt — Production deployment checklist

```text
Task:
Create a production deployment checklist for this SaaS voice agent.

Requirements:
Include:
- environment variables
- database migrations
- seed data
- webhook URLs
- telephony provider setup
- HTTPS/domain setup
- log monitoring
- backup strategy
- rate limits
- webhook verification
- admin auth
- rollback plan
- compliance notes for Bangladesh telecom/call handling

Acceptance criteria:
- Checklist is saved to `docs/deployment_checklist.md`.
- It is practical and not generic.
```

### Prompt — Add health and readiness endpoints

```text
Task:
Add health and readiness endpoints.

Requirements:
- `/health` returns basic app status.
- `/ready` checks DB connectivity and critical configuration.
- Do not expose secrets.

Acceptance criteria:
- Tests cover healthy and DB failure behavior if possible.
- Docker/README references the health endpoint.
```

---

## 23. Release prompts

### Prompt — Prepare v0.1 pilot release

```text
Task:
Prepare the project for a v0.1 pilot release.

Requirements:
- Ensure README has local setup, test, and demo instructions.
- Ensure `.env.example` is complete.
- Ensure demo tenant seed data works.
- Run tests.
- Create `CHANGELOG.md` entry for v0.1.
- Create `docs/pilot_runbook.md` explaining how to onboard a school/university/company.

Acceptance criteria:
- A developer can run the project from README only.
- Pilot runbook includes client onboarding, FAQ collection, test call checklist, and daily unknown-question review.
```

---

## 24. Daily Codex workflow

Use this every development day:

```text
Task:
Review the current repo state and recommend today's next 3 tasks.

Context:
Our goal is to reach a pilot-ready SaaS voice agent for Bangla-English-Sylhet-friendly education and service calls.

Requirements:
- Check docs, tests, TODOs, and current implementation.
- Recommend only tasks that move us toward pilot readiness.
- Prioritize: tenant safety, verified answers, voice flow, unknown-question loop, lead capture, language support.
- Keep recommendations small enough for one Codex task each.

Deliverables:
- 3 tasks with reason, risk, and acceptance criteria.
```

---

## 25. What not to ask Codex

Avoid vague prompts like:

```text
Build the whole SaaS voice agent.
Make it production ready.
Add AI.
Improve everything.
```

Use scoped prompts like:

```text
Implement tenant-scoped FAQ search with tests proving org A cannot access org B data.
```

---

## 26. Recommended phase order

1. Repo audit
2. Docs skeleton
3. Settings + logging
4. Database models + migrations
5. Seed demo tenants
6. Tenant resolver
7. Knowledge search service
8. Language router
9. Answer policy
10. Unknown question loop
11. Voice webhook flow
12. Human handoff
13. Lead capture
14. Admin API
15. CSV import
16. Dashboard skeleton
17. Auth + security
18. Docker + CI
19. Pilot release

---

## 27. First prompt you should paste into Codex now

```text
Context:
We are building a SaaS multilingual AI voice agent for schools, universities, coaching centers, diagnostic centers, consultancies, and service companies.

The system answers phone calls using approved organization knowledge bases, captures leads, logs unknown questions, and transfers to humans when needed. It must support Bangla, English, Banglish, and Sylhet-friendly normalization.

Task:
Audit the current repository and create a development baseline.

Requirements:
- Inspect project structure, dependencies, routes, services, tests, config, and data files.
- Identify what already works and what is missing.
- Identify architecture risks for turning this into a production SaaS.
- Do not modify product code yet.

Deliverables:
- Create `docs/repo_audit.md`.
- Include sections: backend, database/storage, voice webhook, language, tests, deployment, security, and next priorities.
- Give the next 10 development tasks in priority order.
- Run available tests and mention exact commands/results.

Acceptance criteria:
- `docs/repo_audit.md` exists.
- No product code is changed.
- Report is specific to this repo, not generic.
```

---

## 28. Final execution advice

- Keep each Codex task small.
- Always ask for tests.
- Always protect tenant isolation.
- Build the learning loop early.
- Do not overbuild realtime voice before the core answer system is reliable.
- Start pilots with education institutions because admission questions are repetitive and high-value.
