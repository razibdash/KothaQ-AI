from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.storage import create_organization


def test_voice_route_resolves_valid_organization(
    db_client: TestClient,
    db_session: Session,
) -> None:
    create_organization(
        db_session,
        slug="sylhet-university",
        name="Sylhet University",
    )
    db_session.commit()

    response = db_client.post("/api/v1/voice/incoming/sylhet-university")

    assert response.status_code == 200
    assert "Welcome to Sylhet University" in response.text


def test_voice_route_returns_404_for_unknown_organization(
    db_client: TestClient,
) -> None:
    response = db_client.post("/api/v1/voice/incoming/demo")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization 'demo' was not found"}


def test_tenant_api_resolves_organization_from_slug_header(
    db_client: TestClient,
    db_session: Session,
) -> None:
    create_organization(
        db_session,
        slug="api-tenant",
        name="API Tenant",
    )
    db_session.commit()

    valid_response = db_client.get(
        "/api/v1/knowledge/",
        headers={"X-Organization-Slug": "api-tenant"},
    )
    invalid_response = db_client.get(
        "/api/v1/knowledge/",
        headers={"X-Organization-Slug": "missing"},
    )
    missing_header_response = db_client.get("/api/v1/knowledge/")

    assert valid_response.status_code == 200
    assert valid_response.json() == []
    assert invalid_response.status_code == 404
    assert missing_header_response.status_code == 422


def test_voice_route_keeps_tenants_isolated_by_slug(
    db_client: TestClient,
    db_session: Session,
) -> None:
    first = create_organization(
        db_session,
        slug="first-school",
        name="First School",
    )
    second = create_organization(
        db_session,
        slug="second-school",
        name="Second School",
    )
    db_session.commit()

    first_response = db_client.post("/api/v1/voice/incoming/first-school")
    second_response = db_client.post("/api/v1/voice/incoming/second-school")

    assert first.id != second.id
    assert "Welcome to First School" in first_response.text
    assert "Second School" not in first_response.text
    assert "Welcome to Second School" in second_response.text
    assert "First School" not in second_response.text
