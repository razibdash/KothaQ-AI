"""Integration tests for the admin REST API.

Covers:
  • Auth guard — 403 without secret, 503 when key not configured
  • Organizations — list, get by slug, 404 for unknown slug
  • Branches — list, create, get, update, tenant isolation
  • Knowledge items — list, create, get, update, filter by status
  • Status transitions — approve, draft, archive
  • Tenant isolation — one org cannot see or modify another org's data

All tests use the shared ``db_client`` + ``db_session`` fixtures (SQLite
in-memory) from ``conftest.py``.  The admin secret is bypassed via
``app.dependency_overrides`` so no .env file is needed.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.admin_auth import require_admin
from app.main import app
from app.services.storage import TenantStorageService, create_organization

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECRET = "test-admin-secret"
_HEADERS = {"X-Admin-Secret": _SECRET}

_BASE = "/api/v1/admin"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(db_session: Session) -> TestClient:
    """TestClient wired to the in-memory DB with admin auth bypassed."""
    from app.db.session import get_db_session

    def override_db() -> Session:
        yield db_session

    def override_admin() -> None:
        pass  # no-op: bypass shared-secret check

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[require_admin] = override_admin
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def org_a(db_session: Session):
    """Organization A with one branch and one knowledge item."""
    org = create_organization(
        db_session,
        slug="org-alpha",
        name="Alpha University",
        default_language="en-US",
        supported_languages=["en-US"],
    )
    db_session.flush()
    storage = TenantStorageService(db_session, org.id)
    branch = storage.create_branch(slug="main", name="Main Campus")
    storage.create_knowledge_item(
        question="What are your office hours?",
        answer="Monday to Friday, 9am to 5pm.",
        language="en-US",
        status="approved",
    )
    db_session.flush()
    return org


@pytest.fixture
def org_b(db_session: Session):
    """Separate organization to test tenant isolation."""
    org = create_organization(
        db_session,
        slug="org-beta",
        name="Beta College",
        default_language="bn-BD",
        supported_languages=["bn-BD"],
    )
    db_session.flush()
    storage = TenantStorageService(db_session, org.id)
    storage.create_knowledge_item(
        question="ভর্তি কীভাবে করবো?",
        answer="আমাদের ওয়েবসাইটে ভিজিট করুন।",
        language="bn-BD",
        status="draft",
    )
    db_session.flush()
    return org


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


class TestAuthGuard:
    def test_missing_header_returns_422(self, db_client: TestClient) -> None:
        """X-Admin-Secret is required; missing header → 422 validation error."""
        # Note: we use db_client (no auth override) to test the real guard.
        r = db_client.get(f"{_BASE}/organizations")
        assert r.status_code == 422

    def test_wrong_secret_returns_403(self, db_client: TestClient, monkeypatch) -> None:
        """Wrong secret value → 403 Forbidden."""
        import app.api.admin_auth as auth_mod
        import app.core.config as cfg_mod

        monkeypatch.setattr(
            cfg_mod, "get_settings",
            lambda: cfg_mod.Settings(ADMIN_SECRET_KEY=_SECRET),
        )
        monkeypatch.setattr(auth_mod, "get_settings", lambda: cfg_mod.Settings(ADMIN_SECRET_KEY=_SECRET))
        r = db_client.get(
            f"{_BASE}/organizations",
            headers={"X-Admin-Secret": "wrong-value"},
        )
        assert r.status_code == 403

    def test_unconfigured_key_returns_503(self, db_client: TestClient, monkeypatch) -> None:
        """When ADMIN_SECRET_KEY is empty the endpoint is not available (503)."""
        import app.api.admin_auth as auth_mod
        import app.core.config as cfg_mod

        monkeypatch.setattr(
            auth_mod, "get_settings",
            lambda: cfg_mod.Settings(ADMIN_SECRET_KEY=""),
        )
        r = db_client.get(
            f"{_BASE}/organizations",
            headers={"X-Admin-Secret": "anything"},
        )
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


class TestOrganizations:
    def test_list_returns_all_orgs(
        self, admin_client: TestClient, org_a, org_b
    ) -> None:
        r = admin_client.get(f"{_BASE}/organizations")
        assert r.status_code == 200
        slugs = {o["slug"] for o in r.json()}
        assert "org-alpha" in slugs
        assert "org-beta" in slugs

    def test_list_empty_when_no_orgs(self, admin_client: TestClient) -> None:
        r = admin_client.get(f"{_BASE}/organizations")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_org_by_slug(self, admin_client: TestClient, org_a) -> None:
        r = admin_client.get(f"{_BASE}/organizations/org-alpha")
        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "org-alpha"
        assert data["name"] == "Alpha University"
        assert "id" in data
        assert "created_at" in data

    def test_get_org_unknown_slug_returns_404(self, admin_client: TestClient) -> None:
        r = admin_client.get(f"{_BASE}/organizations/does-not-exist")
        assert r.status_code == 404

    def test_org_read_schema_fields(self, admin_client: TestClient, org_a) -> None:
        r = admin_client.get(f"{_BASE}/organizations/org-alpha")
        data = r.json()
        for field in ("id", "slug", "name", "default_language", "supported_languages", "timezone", "created_at"):
            assert field in data, f"Expected field '{field}' in response"


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


class TestBranches:
    def test_list_branches(self, admin_client: TestClient, org_a) -> None:
        r = admin_client.get(f"{_BASE}/organizations/org-alpha/branches")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["slug"] == "main"

    def test_list_branches_empty_for_new_org(
        self, admin_client: TestClient, org_b
    ) -> None:
        r = admin_client.get(f"{_BASE}/organizations/org-beta/branches")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_branch(self, admin_client: TestClient, org_a) -> None:
        payload = {
            "slug": "north-campus",
            "name": "North Campus",
            "city": "Sylhet",
            "country": "BD",
            "timezone": "Asia/Dhaka",
        }
        r = admin_client.post(f"{_BASE}/organizations/org-alpha/branches", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == "north-campus"
        assert data["city"] == "Sylhet"
        assert data["organization_id"] == str(org_a.id)

    def test_create_branch_validates_slug_pattern(
        self, admin_client: TestClient, org_a
    ) -> None:
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/branches",
            json={"slug": "UPPER CASE", "name": "Bad"},
        )
        assert r.status_code == 422

    def test_create_branch_unknown_org_returns_404(
        self, admin_client: TestClient
    ) -> None:
        r = admin_client.post(
            f"{_BASE}/organizations/ghost-org/branches",
            json={"slug": "x", "name": "X"},
        )
        assert r.status_code == 404

    def test_get_branch(self, admin_client: TestClient, org_a, db_session: Session) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        branches = storage.list_branches()
        branch_id = str(branches[0].id)

        r = admin_client.get(f"{_BASE}/organizations/org-alpha/branches/{branch_id}")
        assert r.status_code == 200
        assert r.json()["id"] == branch_id

    def test_get_branch_returns_404_for_unknown(
        self, admin_client: TestClient, org_a
    ) -> None:
        r = admin_client.get(
            f"{_BASE}/organizations/org-alpha/branches/{uuid4()}"
        )
        assert r.status_code == 404

    def test_update_branch(self, admin_client: TestClient, org_a, db_session: Session) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        branch_id = str(storage.list_branches()[0].id)

        r = admin_client.patch(
            f"{_BASE}/organizations/org-alpha/branches/{branch_id}",
            json={"city": "Dhaka", "phone": "+8801700000000"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["city"] == "Dhaka"
        assert data["phone"] == "+8801700000000"
        # Unset fields unchanged
        assert data["name"] == "Main Campus"

    def test_update_branch_empty_body_is_no_op(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        branch_id = str(storage.list_branches()[0].id)

        r = admin_client.patch(
            f"{_BASE}/organizations/org-alpha/branches/{branch_id}",
            json={},
        )
        assert r.status_code == 200

    def test_branch_tenant_isolation(
        self, admin_client: TestClient, org_a, org_b, db_session: Session
    ) -> None:
        """Branch from org_a must not be visible via org_b's endpoint."""
        storage_a = TenantStorageService(db_session, org_a.id)
        branch_id = str(storage_a.list_branches()[0].id)

        r = admin_client.get(
            f"{_BASE}/organizations/org-beta/branches/{branch_id}"
        )
        assert r.status_code == 404

    def test_branch_update_tenant_isolation(
        self, admin_client: TestClient, org_a, org_b, db_session: Session
    ) -> None:
        """Cannot update org_a's branch via org_b's URL."""
        storage_a = TenantStorageService(db_session, org_a.id)
        branch_id = str(storage_a.list_branches()[0].id)

        r = admin_client.patch(
            f"{_BASE}/organizations/org-beta/branches/{branch_id}",
            json={"name": "Hijacked"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Knowledge items
# ---------------------------------------------------------------------------


class TestKnowledgeItems:
    def test_list_knowledge_items(self, admin_client: TestClient, org_a) -> None:
        r = admin_client.get(f"{_BASE}/organizations/org-alpha/knowledge")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["status"] == "approved"

    def test_list_filters_by_status(
        self, admin_client: TestClient, org_a, org_b
    ) -> None:
        # org_b has one draft item
        r = admin_client.get(
            f"{_BASE}/organizations/org-beta/knowledge?status=draft"
        )
        assert r.status_code == 200
        assert all(i["status"] == "draft" for i in r.json())

        r2 = admin_client.get(
            f"{_BASE}/organizations/org-beta/knowledge?status=approved"
        )
        assert r2.status_code == 200
        assert r2.json() == []

    def test_create_knowledge_item(self, admin_client: TestClient, org_a) -> None:
        payload = {
            "question": "When is registration?",
            "answer": "Registration is in January.",
            "language": "en-US",
            "status": "draft",
            "tags": ["registration", "dates"],
        }
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/knowledge", json=payload
        )
        assert r.status_code == 201
        data = r.json()
        assert data["question"] == "When is registration?"
        assert data["tags"] == ["registration", "dates"]
        assert data["status"] == "draft"
        assert data["organization_id"] == str(org_a.id)

    def test_create_knowledge_item_invalid_branch_returns_422(
        self, admin_client: TestClient, org_a
    ) -> None:
        """branch_id from a different org must be rejected."""
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/knowledge",
            json={
                "question": "Q",
                "answer": "A",
                "branch_id": str(uuid4()),  # non-existent branch
            },
        )
        assert r.status_code == 422

    def test_get_knowledge_item(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        item_id = str(storage.list_knowledge_items()[0].id)

        r = admin_client.get(
            f"{_BASE}/organizations/org-alpha/knowledge/{item_id}"
        )
        assert r.status_code == 200
        assert r.json()["id"] == item_id

    def test_get_knowledge_item_404_for_unknown(
        self, admin_client: TestClient, org_a
    ) -> None:
        r = admin_client.get(
            f"{_BASE}/organizations/org-alpha/knowledge/{uuid4()}"
        )
        assert r.status_code == 404

    def test_update_knowledge_item(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        item_id = str(storage.list_knowledge_items()[0].id)

        r = admin_client.patch(
            f"{_BASE}/organizations/org-alpha/knowledge/{item_id}",
            json={"answer": "Monday to Friday, 8am to 6pm.", "tags": ["hours"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "Monday to Friday, 8am to 6pm."
        assert data["tags"] == ["hours"]

    def test_update_does_not_change_unset_fields(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        storage = TenantStorageService(db_session, org_a.id)
        item = storage.list_knowledge_items()[0]
        item_id = str(item.id)
        original_question = item.question

        r = admin_client.patch(
            f"{_BASE}/organizations/org-alpha/knowledge/{item_id}",
            json={"answer": "Updated answer only."},
        )
        assert r.status_code == 200
        assert r.json()["question"] == original_question

    def test_knowledge_tenant_isolation_get(
        self, admin_client: TestClient, org_a, org_b, db_session: Session
    ) -> None:
        """org_a item must not be visible via org_b endpoint."""
        storage_a = TenantStorageService(db_session, org_a.id)
        item_id = str(storage_a.list_knowledge_items()[0].id)

        r = admin_client.get(
            f"{_BASE}/organizations/org-beta/knowledge/{item_id}"
        )
        assert r.status_code == 404

    def test_knowledge_tenant_isolation_update(
        self, admin_client: TestClient, org_a, org_b, db_session: Session
    ) -> None:
        """Cannot update org_a's item via org_b's URL."""
        storage_a = TenantStorageService(db_session, org_a.id)
        item_id = str(storage_a.list_knowledge_items()[0].id)

        r = admin_client.patch(
            f"{_BASE}/organizations/org-beta/knowledge/{item_id}",
            json={"answer": "Hijacked."},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class TestKnowledgeStatusTransitions:
    def _get_item_id(self, db_session: Session, org) -> str:
        storage = TenantStorageService(db_session, org.id)
        return str(storage.list_knowledge_items()[0].id)

    def test_approve_sets_status(
        self, admin_client: TestClient, org_b, db_session: Session
    ) -> None:
        """org_b has a draft item — approve it."""
        item_id = self._get_item_id(db_session, org_b)
        r = admin_client.post(
            f"{_BASE}/organizations/org-beta/knowledge/{item_id}/approve"
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_draft_reverts_status(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        """org_a has an approved item — revert to draft."""
        item_id = self._get_item_id(db_session, org_a)
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/knowledge/{item_id}/draft"
        )
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_archive_sets_status(
        self, admin_client: TestClient, org_a, db_session: Session
    ) -> None:
        item_id = self._get_item_id(db_session, org_a)
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/knowledge/{item_id}/archive"
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_approve_then_archive_then_draft(
        self, admin_client: TestClient, org_b, db_session: Session
    ) -> None:
        """Full status lifecycle roundtrip."""
        item_id = self._get_item_id(db_session, org_b)
        base = f"{_BASE}/organizations/org-beta/knowledge/{item_id}"

        assert admin_client.post(f"{base}/approve").json()["status"] == "approved"
        assert admin_client.post(f"{base}/archive").json()["status"] == "archived"
        assert admin_client.post(f"{base}/draft").json()["status"] == "draft"

    def test_status_action_unknown_item_returns_404(
        self, admin_client: TestClient, org_a
    ) -> None:
        r = admin_client.post(
            f"{_BASE}/organizations/org-alpha/knowledge/{uuid4()}/approve"
        )
        assert r.status_code == 404

    def test_status_action_tenant_isolation(
        self, admin_client: TestClient, org_a, org_b, db_session: Session
    ) -> None:
        """Cannot transition org_a's item via org_b's URL."""
        storage_a = TenantStorageService(db_session, org_a.id)
        item_id = str(storage_a.list_knowledge_items()[0].id)

        r = admin_client.post(
            f"{_BASE}/organizations/org-beta/knowledge/{item_id}/archive"
        )
        assert r.status_code == 404
