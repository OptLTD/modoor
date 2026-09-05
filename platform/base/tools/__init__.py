"""Base module MCP tools — App / User / Role."""

from __future__ import annotations

from modoor.runtime.confirmation import (
    issue_confirmation_token,
    needs_confirmation_payload,
    verify_confirmation_token,
)
from modoor.runtime.tool import run_tool
from platform.base import domain as base_domain


def _delete_with_confirm(
    *,
    tool: str,
    confirm_args: dict,
    summary: dict,
    confirmation_token: str | None,
    do_delete,
):
    def _inner(session, ctx, settings):
        # ensure target exists & build summary via caller-provided summary already
        if confirmation_token:
            verify_confirmation_token(
                secret=settings.modoor_confirm_secret,
                ctx=ctx,
                tool=tool,
                args=confirm_args,
                token=confirmation_token,
            )
            return do_delete(session, ctx)

        token, expires_at = issue_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool=tool,
            args=confirm_args,
            ttl_seconds=settings.modoor_confirm_ttl_seconds,
        )
        return needs_confirmation_payload(
            token=token,
            expires_at=expires_at,
            tool=tool,
            summary=summary,
            args=confirm_args,
        )

    return _inner


def create_app(code: str, name: str, description: str | None = None) -> str:
    """Create an application under the current tenant."""
    args = {"code": code, "name": name, "description": description}

    def _inner(session, ctx, _settings):
        return base_domain.create_app(
            session, ctx, code=code, name=name, description=description
        )

    return run_tool("base.create_app", args, _inner)


def update_app(
    app_id: str | None = None,
    code: str | None = None,
    name: str | None = None,
    description: str | None = None,
    active: bool | None = None,
) -> str:
    """Update an app (by app_id or code)."""
    args = {
        "app_id": app_id,
        "code": code,
        "name": name,
        "description": description,
        "active": active,
    }

    def _inner(session, ctx, _settings):
        return base_domain.update_app(
            session,
            ctx,
            app_id=app_id,
            code=code,
            name=name,
            description=description,
            active=active,
        )

    return run_tool("base.update_app", args, _inner)


def get_app(app_id: str | None = None, code: str | None = None) -> str:
    """Get an app by id or code."""
    args = {"app_id": app_id, "code": code}

    def _inner(session, ctx, _settings):
        return base_domain.get_app(session, ctx, app_id=app_id, code=code)

    return run_tool("base.get_app", args, _inner)


def list_apps(q: str | None = None, limit: int = 50) -> str:
    """List apps in the current tenant."""
    args = {"q": q, "limit": limit}

    def _inner(session, ctx, _settings):
        return base_domain.list_apps(session, ctx, q=q, limit=limit)

    return run_tool("base.list_apps", args, _inner)


def delete_app(
    app_id: str | None = None,
    code: str | None = None,
    confirmation_token: str | None = None,
) -> str:
    """Delete an app (high risk). Fails if roles still reference it."""
    confirm_args = {"app_id": app_id, "code": code}
    args = {**confirm_args, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        app = base_domain.get_app(session, ctx, app_id=app_id, code=code)
        return _delete_with_confirm(
            tool="base.delete_app",
            confirm_args=confirm_args,
            summary={"id": app["id"], "code": app["code"], "name": app["name"]},
            confirmation_token=confirmation_token,
            do_delete=lambda s, c: base_domain.delete_app(
                s, c, app_id=app_id, code=code
            ),
        )(session, ctx, settings)

    return run_tool("base.delete_app", args, _inner)


def create_user(username: str, realname: str, email: str | None = None, password: str | None = None) -> str:
    """Create a user under the current tenant."""
    args = {
        "username": username,
        "realname": realname,
        "email": email,
        "password": "***" if password else None,
    }

    def _inner(session, ctx, _settings):
        return base_domain.create_user(
            session,
            ctx,
            username=username,
            realname=realname,
            email=email,
            password=password,
        )

    return run_tool("base.create_user", args, _inner)


def update_user(
    user_id: int | None = None,
    username: str | None = None,
    realname: str | None = None,
    email: str | None = None,
    active: bool | None = None,
    password: str | None = None,
) -> str:
    """Update a user (by user_id or username)."""
    args = {
        "user_id": user_id,
        "username": username,
        "realname": realname,
        "email": email,
        "active": active,
        "password": "***" if password else None,
    }

    def _inner(session, ctx, _settings):
        return base_domain.update_user(
            session,
            ctx,
            user_id=user_id,
            username=username,
            realname=realname,
            email=email,
            active=active,
            password=password,
        )

    return run_tool("base.update_user", args, _inner)


def get_user(user_id: int | None = None, username: str | None = None) -> str:
    """Get a user by id or username."""
    args = {"user_id": user_id, "username": username}

    def _inner(session, ctx, _settings):
        return base_domain.get_user(session, ctx, user_id=user_id, username=username)

    return run_tool("base.get_user", args, _inner)


def list_users(q: str | None = None, limit: int = 50) -> str:
    """List users in the current tenant."""
    args = {"q": q, "limit": limit}

    def _inner(session, ctx, _settings):
        return base_domain.list_users(session, ctx, q=q, limit=limit)

    return run_tool("base.list_users", args, _inner)


def delete_user(
    user_id: int | None = None,
    username: str | None = None,
    confirmation_token: str | None = None,
) -> str:
    """Delete a user (high risk). Also removes role assignments."""
    confirm_args = {"user_id": user_id, "username": username}
    args = {**confirm_args, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        user = base_domain.get_user(session, ctx, user_id=user_id, username=username)
        return _delete_with_confirm(
            tool="base.delete_user",
            confirm_args=confirm_args,
            summary={
                "id": user["id"],
                "username": user["username"],
                "realname": user["realname"],
            },
            confirmation_token=confirmation_token,
            do_delete=lambda s, c: base_domain.delete_user(
                s, c, user_id=user_id, username=username
            ),
        )(session, ctx, settings)

    return run_tool("base.delete_user", args, _inner)


def create_role(
    name: str,
    code: str | None = None,
    description: str | None = None,
) -> str:
    """Create a tenant-wide role. Omit code to auto-generate (role#####)."""
    args = {
        "code": code,
        "name": name,
        "description": description,
    }

    def _inner(session, ctx, _settings):
        return base_domain.create_role(
            session,
            ctx,
            code=code,
            name=name,
            description=description,
        )

    return run_tool("base.create_role", args, _inner)


def update_role(
    role_id: str | None = None,
    code: str | None = None,
    name: str | None = None,
    description: str | None = None,
    active: bool | None = None,
) -> str:
    """Update a role (by role_id or code)."""
    args = {
        "role_id": role_id,
        "code": code,
        "name": name,
        "description": description,
        "active": active,
    }

    def _inner(session, ctx, _settings):
        return base_domain.update_role(
            session,
            ctx,
            role_id=role_id,
            code=code,
            name=name,
            description=description,
            active=active,
        )

    return run_tool("base.update_role", args, _inner)


def get_role(
    role_id: str | None = None,
    code: str | None = None,
) -> str:
    """Get a role by id or code."""
    args = {"role_id": role_id, "code": code}

    def _inner(session, ctx, _settings):
        return base_domain.get_role(session, ctx, role_id=role_id, code=code)

    return run_tool("base.get_role", args, _inner)


def list_roles(q: str | None = None, limit: int = 50) -> str:
    """List roles in the current tenant."""
    args = {"q": q, "limit": limit}

    def _inner(session, ctx, _settings):
        return base_domain.list_roles(session, ctx, q=q, limit=limit)

    return run_tool("base.list_roles", args, _inner)


def delete_role(
    role_id: str | None = None,
    code: str | None = None,
    confirmation_token: str | None = None,
) -> str:
    """Delete a role (high risk). Also removes assignments."""
    confirm_args = {"role_id": role_id, "code": code}
    args = {**confirm_args, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        role = base_domain.get_role(session, ctx, role_id=role_id, code=code)
        return _delete_with_confirm(
            tool="base.delete_role",
            confirm_args=confirm_args,
            summary={
                "id": role["id"],
                "code": role["code"],
                "name": role["name"],
            },
            confirmation_token=confirmation_token,
            do_delete=lambda s, c: base_domain.delete_role(
                s, c, role_id=role_id, code=code
            ),
        )(session, ctx, settings)

    return run_tool("base.delete_role", args, _inner)


def assign_role(user_id: str, role_id: str) -> str:
    """Assign a role to a user."""
    args = {"user_id": user_id, "role_id": role_id}

    def _inner(session, ctx, _settings):
        return base_domain.assign_role(
            session, ctx, user_id=user_id, role_id=role_id
        )

    return run_tool("base.assign_role", args, _inner)


def revoke_role(
    user_id: str,
    role_id: str,
    confirmation_token: str | None = None,
) -> str:
    """Revoke a role from a user (high risk)."""
    confirm_args = {"user_id": user_id, "role_id": role_id}
    args = {**confirm_args, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        roles = base_domain.list_user_roles(session, ctx, user_id=user_id)
        return _delete_with_confirm(
            tool="base.revoke_role",
            confirm_args=confirm_args,
            summary={"user_id": user_id, "role_id": role_id, "roles": roles["count"]},
            confirmation_token=confirmation_token,
            do_delete=lambda s, c: base_domain.revoke_role(
                s, c, user_id=user_id, role_id=role_id
            ),
        )(session, ctx, settings)

    return run_tool("base.revoke_role", args, _inner)


def list_user_roles(user_id: str) -> str:
    """List roles assigned to a user."""
    args = {"user_id": user_id}

    def _inner(session, ctx, _settings):
        return base_domain.list_user_roles(session, ctx, user_id=user_id)

    return run_tool("base.list_user_roles", args, _inner)


def list_modules() -> str:
    """List discovered modules and their enabled state for the current tenant."""
    from modoor.platform.module_state import list_modules as _list
    from modoor.platform.module_state import sync_discovered_modules

    def _inner(session, ctx, settings):
        sync_discovered_modules(session, ctx.tenant, settings)
        return {"items": _list(session, ctx.tenant, settings=settings)}

    return run_tool("base.list_modules", {}, _inner)


def set_module_enabled(module_id: str, enabled: bool) -> str:
    """Enable or disable a module for the current tenant (base cannot be disabled)."""
    from modoor.platform.module_state import set_module_enabled as _set

    args = {"module_id": module_id, "enabled": enabled}

    def _inner(session, ctx, _settings):
        return _set(session, ctx.tenant, module_id, enabled)

    return run_tool("base.set_module_enabled", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="base.create_app")(create_app)
    mcp.tool(name="base.update_app")(update_app)
    mcp.tool(name="base.get_app")(get_app)
    mcp.tool(name="base.list_apps")(list_apps)
    mcp.tool(name="base.delete_app")(delete_app)

    mcp.tool(name="base.create_user")(create_user)
    mcp.tool(name="base.update_user")(update_user)
    mcp.tool(name="base.get_user")(get_user)
    mcp.tool(name="base.list_users")(list_users)
    mcp.tool(name="base.delete_user")(delete_user)

    mcp.tool(name="base.create_role")(create_role)
    mcp.tool(name="base.update_role")(update_role)
    mcp.tool(name="base.get_role")(get_role)
    mcp.tool(name="base.list_roles")(list_roles)
    mcp.tool(name="base.delete_role")(delete_role)

    mcp.tool(name="base.assign_role")(assign_role)
    mcp.tool(name="base.revoke_role")(revoke_role)
    mcp.tool(name="base.list_user_roles")(list_user_roles)

    mcp.tool(name="base.list_modules")(list_modules)
    mcp.tool(name="base.set_module_enabled")(set_module_enabled)
