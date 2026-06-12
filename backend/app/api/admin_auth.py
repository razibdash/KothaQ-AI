"""Admin API authentication — shared-secret placeholder.

⚠  SECURITY NOTICE — READ BEFORE DEPLOYING  ⚠
===============================================
This module provides a *development-grade* authentication guard for admin
endpoints.  It compares the ``X-Admin-Secret`` request header against the
``ADMIN_SECRET_KEY`` environment variable using a constant-time comparison
to prevent timing attacks.

THIS IS NOT PRODUCTION-READY.  Before going live:

1.  Replace ``require_admin`` with a proper JWT or OAuth2 dependency that
    validates a signed token issued by your identity provider.
2.  Add per-user admin accounts so actions can be attributed to a person.
3.  Implement an audit log for all admin mutations.
4.  Rotate ``ADMIN_SECRET_KEY`` and remove it from ``.env.example``.

How to enable admin endpoints in development
-------------------------------------------
Set ``ADMIN_SECRET_KEY`` in your ``.env`` file (or environment):

    ADMIN_SECRET_KEY=change-me-before-production

Then include the header in every admin request:

    X-Admin-Secret: change-me-before-production

A 503 is returned when the key is not configured (fail-safe default).
A 403 is returned when the header value does not match.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings


def require_admin(
    x_admin_secret: Annotated[str, Header(alias="X-Admin-Secret")],
) -> None:
    """FastAPI dependency that enforces the admin shared-secret gate.

    Inject via ``Depends(require_admin)`` or the ``AdminAuth`` shorthand.
    The dependency produces no return value; it raises on failure.

    Raises
    ------
    HTTPException 503 — ``ADMIN_SECRET_KEY`` is not configured.
    HTTPException 403 — Header value does not match the configured key.
    """
    configured_key = get_settings().ADMIN_SECRET_KEY
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Admin endpoints are not configured. "
                "Set ADMIN_SECRET_KEY in your environment — "
                "see app/api/admin_auth.py for the full security notice."
            ),
        )
    if not secrets.compare_digest(x_admin_secret, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret.",
        )


# Convenience annotation — attach to any router or endpoint:
#   router = APIRouter(dependencies=[AdminAuth])
AdminAuth = Depends(require_admin)
