# Backend

FastAPI backend for the SaaS voice agent.

## Key modules

```txt
app/api/v1/endpoints/      HTTP endpoints
app/core/                  settings, security, logging
app/db/                    database session and migrations
app/models/                SQLAlchemy models
app/schemas/               Pydantic request/response schemas
app/services/voice/        call orchestration
app/services/ai/           LLM and response policy
app/services/knowledge/    FAQ/RAG search
app/services/language/     Bangla/Banglish/Sylhet routing
app/services/telephony/    Twilio/SIP adapters
app/workers/               async jobs
```
