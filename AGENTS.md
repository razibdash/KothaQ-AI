# AI Agent Instructions

You are building a multilingual SaaS voice agent platform.

## Product rules

- This is a multi-tenant SaaS product. Never write code that can leak one organization's data to another organization.
- The agent must answer from approved organization knowledge only.
- If confidence is low, log an unknown question and offer human handoff.
- Support Bangla, English, Banglish, and Sylhet-friendly normalization.
- Prefer small, testable changes.

## Backend rules

- Use FastAPI service/controller pattern.
- Keep business logic in `app/services`, not in route handlers.
- Use Pydantic schemas for request/response validation.
- Use SQLAlchemy/Alembic for database changes.
- Write tests for every new feature.

## Frontend rules

- Use Next.js App Router.
- Keep API calls in `src/lib/api` or feature modules.
- Components should be reusable and typed.
- Do not hardcode organization IDs in UI.

## Safety rules

- Never expose secrets.
- Never store raw credentials in git.
- Add migration and tests when changing persistence.

```

```
