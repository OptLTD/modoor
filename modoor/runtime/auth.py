from __future__ import annotations

from sqlalchemy import select

from modoor.core.ctx import Ctx
from modoor.core.db import session_scope
from modoor.core.errors import AppError
from modoor.core.settings import Settings
from platform.base.domain import SystemUser, ensure_tenant, root_team_id


def resolve_ctx(settings: Settings, provided_api_key: str | None = None) -> Ctx:
    """Phase 0: one process maps one API key to a fixed ctx via env + DB."""
    expected = settings.modoor_api_key
    key = provided_api_key if provided_api_key is not None else expected
    if not key or key != expected:
        raise AppError(
            code="permission_denied",
            message="Invalid or missing API key",
        )
    with session_scope() as session:
        ensured = ensure_tenant(
            session, settings.modoor_tenant, tenant_id=settings.modoor_tenant_id
        )
        tenant_id = int(ensured["tenant"]["id"])
        team_id = settings.modoor_team_id
        if team_id is None:
            team_id = root_team_id(session, tenant_id)
        user_id = settings.modoor_user_id
        if user_id is None:
            row = session.scalar(
                select(SystemUser)
                .where(SystemUser.tenant == tenant_id)
                .order_by(SystemUser.id)
            )
            user_id = int(row.id) if row else 0
        return Ctx(tenant=tenant_id, user_id=user_id, team_id=team_id)
