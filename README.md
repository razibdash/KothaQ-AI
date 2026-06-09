# Multilingual SaaS Voice Agent — Project Structure

This is a production-oriented monorepo scaffold for a SaaS AI voice receptionist/voice agent.
It supports schools, universities, coaching centers, diagnostic centers, consultancies, and service companies.

Core goals:

- Multi-tenant SaaS backend
- Bangla, English, Banglish, and Sylhet-friendly normalization
- Phone voice webhook layer
- Verified knowledge-base answers
- Unknown-question learning loop
- Lead capture and human handoff
- Admin dashboard
- International-ready language architecture

## Top-level structure

```txt
voice-agent-saas-structure/
├── backend/        # FastAPI API, workers, database, AI/voice services
├── frontend/       # Next.js admin dashboard
├── shared/         # Shared contracts, prompts, sample org/FAQ data
├── docs/           # Architecture, product decisions, runbooks
├── infra/          # Docker, nginx, Terraform/deployment templates
├── scripts/        # Developer scripts
└── .github/        # CI workflows
```

## Recommended development order

1. Backend settings, logging, health check
2. PostgreSQL models and migrations
3. Organization/tenant resolver
4. Knowledge base CRUD and search
5. Language router: Bangla, English, Banglish, Sylhet-friendly
6. Voice webhook and call-turn logging
7. Unknown-question learning loop
8. Lead capture and human handoff
9. Frontend dashboard
10. Auth, billing, analytics, deployment hardening
```
