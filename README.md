# Talkque

Talkque is a multilingual SaaS voice agent platform for schools,
universities, and service companies. The target product answers calls from
organization-approved knowledge, supports Bangla, English, Banglish, and
Sylhet-friendly conversations, captures leads, logs unknown questions, and
offers human handoff.

> Status: early development scaffold. Health endpoints and basic project
> structure exist, but authentication, tenant persistence, verified retrieval,
> production voice orchestration, and dashboard workflows are not complete.

## Product Principles

- Keep every organization's data and knowledge isolated.
- Answer only from approved organization knowledge.
- When confidence is low, do not guess; log the question and offer handoff.
- Preserve the caller's language and use short, natural voice responses.
- Keep business logic in testable backend services.

## Voice Pipeline

```text
Phone call
  -> telephony webhook
  -> speech-to-text or provider input
  -> language router and normalization
  -> approved knowledge retrieval or intent handling
  -> verified answer policy
  -> response generation and text-to-speech
  -> call, lead, unknown-question, and handoff logs
```

See [docs/architecture.md](docs/architecture.md) for component boundaries and
failure behavior.

## Repository Layout

```text
backend/   FastAPI API, services, schemas, models, and tests
frontend/  Next.js App Router administration dashboard
shared/    API contract drafts, prompts, and sample multilingual data
infra/     Docker, nginx, and deployment scaffolding
docs/      Architecture, product rules, plans, setup, and audit
scripts/   Local development launch helpers
```

## Quick Start

Prerequisites:

- Python 3.11 or newer
- Node.js 22 or newer with npm
- Docker Desktop or Docker Engine with Compose, for PostgreSQL and Redis

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Frontend, in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`
- FastAPI docs: `http://localhost:8000/docs`

The example environment file contains placeholders only. Put real local
credentials in `backend/.env`, never in tracked files. Full setup and
troubleshooting are in [docs/local_setup.md](docs/local_setup.md).

## Development

Run backend tests:

```powershell
cd backend
python -m pytest -q
```

Run the frontend build:

```powershell
cd frontend
npm run build
```

New backend behavior requires tests. Persistence changes require SQLAlchemy
models, an Alembic migration, and tenant-isolation coverage.

## Documentation

- [Architecture](docs/architecture.md)
- [Development plan](docs/development_plan.md)
- [Local setup](docs/local_setup.md)
- [Product rules](docs/product_rules.md)
- [Repository audit](docs/repo_audit.md)
