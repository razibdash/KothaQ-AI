# API Contract Draft

## Organization

- `GET /api/v1/organizations`
- `POST /api/v1/organizations`

## Knowledge Base

- `GET /api/v1/knowledge`
- `POST /api/v1/knowledge`
- `POST /api/v1/knowledge/search`

## Voice

- `POST /api/v1/voice/incoming/{organization_slug}`
- `POST /api/v1/voice/turn/{call_id}`

## Unknown Questions

- `GET /api/v1/unknown-questions`
- `POST /api/v1/unknown-questions/{id}/approve`
