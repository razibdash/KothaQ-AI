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

## Knowledge CSV import

Admin endpoint:

```http
POST /api/v1/admin/organizations/{org_slug}/knowledge/import-csv
Content-Type: multipart/form-data
X-Admin-Secret: <admin-secret>
```

Upload the CSV as the `file` form field. Required columns are `question`,
`answer`, and `language`. Optional columns are `branch_slug`, `tags`, `status`,
and `source_reference`.

```csv
question,answer,language,branch_slug,tags,status,source_reference
When is tuition due?,Tuition is due by 10 January.,en-US,main,billing;tuition,,tuition-2026
How do I apply?,Apply through the admissions portal.,en-US,,admissions,approved,apply-2026
```

Rows without `status` are imported as `draft`. Use `approved` explicitly when a
row is ready for caller-facing answers. Invalid or duplicate rows are skipped
and returned with row-level errors in the import response.
