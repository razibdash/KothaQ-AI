"""Admin API router — all routes require the X-Admin-Secret header.

Route map
---------
GET  /admin/organizations                                      list orgs
GET  /admin/organizations/{org_slug}                           get org

GET  /admin/organizations/{org_slug}/branches                  list branches
POST /admin/organizations/{org_slug}/branches                  create branch
GET  /admin/organizations/{org_slug}/branches/{branch_id}      get branch
PATCH /admin/organizations/{org_slug}/branches/{branch_id}     update branch

GET   /admin/organizations/{org_slug}/knowledge                list items
POST  /admin/organizations/{org_slug}/knowledge                create item
GET   /admin/organizations/{org_slug}/knowledge/{item_id}      get item
PATCH /admin/organizations/{org_slug}/knowledge/{item_id}      update item
POST  /admin/organizations/{org_slug}/knowledge/{item_id}/approve  → approved
POST  /admin/organizations/{org_slug}/knowledge/{item_id}/draft    → draft
POST  /admin/organizations/{org_slug}/knowledge/{item_id}/archive  → archived
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.admin_auth import AdminAuth
from app.api.v1.admin import branches, knowledge, organizations

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[AdminAuth],
)

admin_router.include_router(
    organizations.router,
    prefix="/organizations",
)
admin_router.include_router(
    branches.router,
    prefix="/organizations/{org_slug}/branches",
)
admin_router.include_router(
    knowledge.router,
    prefix="/organizations/{org_slug}/knowledge",
)
