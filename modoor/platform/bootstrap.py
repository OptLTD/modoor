"""Bootstrap seed data for local / first-run."""

from __future__ import annotations

from sqlalchemy import select

from modoor.core.ctx import Ctx
from modoor.core.db import session_scope
from modoor.core.errors import AppError
from modoor.core.security import hash_password
from modoor.core.settings import Settings, get_settings
from modoor.platform.module_state import sync_discovered_modules
from modules.base.domain import SystemUser
from modules.base import domain as base_domain
from modules.sale import domain as sale_domain
from modules.wiki import domain as wiki_domain


def bootstrap(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    tenant_name = settings.modoor_tenant
    admin_username = settings.modoor_admin_username
    admin_password = settings.modoor_admin_password

    created = {
        "tenant": False,
        "root_team": False,
        "admin_user": False,
        "admin_role": False,
        "main_app": False,
        "welcome_wiki": False,
        "admin_password_reset": False,
        "sale_demo_orders": 0,
    }

    with session_scope() as session:
        ensured = base_domain.ensure_tenant(session, tenant_name)
        tenant_id = ensured["tenant"]["id"]
        team_id = ensured["team"]["id"]
        created["tenant"] = ensured["created_tenant"]
        created["root_team"] = ensured["created_team"]

        sync_discovered_modules(session, tenant_id, settings)

        bootstrap_ctx = Ctx(tenant=tenant_id, user_id=0, team_id=team_id)

        try:
            admin = base_domain.get_user(session, bootstrap_ctx, username=admin_username)
        except AppError:
            admin = base_domain.create_user(
                session,
                bootstrap_ctx,
                username=admin_username,
                realname="Administrator",
                password=admin_password,
                team_id=team_id,
            )
            created["admin_user"] = True

        admin_id = int(admin["id"])
        row = session.scalar(
            select(SystemUser).where(
                SystemUser.tenant == tenant_id, SystemUser.username == admin_username
            )
        )
        if row and not row.password:
            row.password = hash_password(admin_password)
            created["admin_password_reset"] = True
        if row and row.team_id != team_id:
            row.team_id = team_id

        ctx = Ctx(tenant=tenant_id, user_id=admin_id, team_id=team_id)

        try:
            base_domain.get_app(session, ctx, code="main")
        except AppError:
            base_domain.create_app(
                session,
                ctx,
                code="main",
                name="Main App",
                description="Default application",
            )
            created["main_app"] = True

        try:
            role = base_domain.get_role(session, ctx, code="admin")
        except AppError:
            role = base_domain.create_role(
                session,
                ctx,
                code="admin",
                name="Administrator",
                description="Full access",
            )
            created["admin_role"] = True

        role_id = role["id"]
        roles = base_domain.list_user_roles(session, ctx, user_id=admin_id)
        if not any(r["id"] == role_id for r in roles["roles"]):
            base_domain.assign_role(session, ctx, user_id=admin_id, role_id=role_id)

        projects = wiki_domain.list_projects(session, ctx)
        if projects["count"] == 0:
            created_proj = wiki_domain.create_project(
                session,
                ctx,
                name="General",
                description="Default wiki project",
                home_title="Welcome",
            )
            home_id = created_proj["home_page"]["id"]
            wiki_domain.update_page(
                session,
                ctx,
                page_id=home_id,
                title="Welcome",
                body=wiki_domain.markdown_to_blocks_json(
                    "# Welcome to Modoor\n\n"
                    "Bootstrap created this project.\n\n"
                    f"- Username: `{admin_username}`\n"
                    "- Open Base module for users and roles.\n"
                ),
            )
            created["welcome_wiki"] = True

        created["sale_demo_orders"] = sale_domain.seed_demo_orders(session, ctx)

    return {
        "tenant": tenant_name,
        "tenant_id": tenant_id,
        "team_id": team_id,
        "admin_username": admin_username,
        "created": created,
    }
