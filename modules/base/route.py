"""modules.base JSON API for Vue views."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from modoor.core.db import session_scope
from modoor.platform.module_state import list_modules, set_module_enabled, sync_discovered_modules
from modoor.web.api_util import ctx_of, http_error, kit, require_user
from modoor.web.nav import clear_ui_cache
from modules.base import domain as base_domain

router = APIRouter(prefix="/api/base", tags=["base"])


class UserCreate(BaseModel):
    username: str
    realname: str
    email: str | None = None
    password: str
    team_id: int | None = None


class UserUpdate(BaseModel):
    realname: str | None = None
    email: str | None = None
    active: bool | None = None
    password: str | None = None
    team_id: int | None = None


class TeamCreate(BaseModel):
    name: str
    parent: int | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    parent: int | None = None
    active: bool | None = None


class RoleCreate(BaseModel):
    code: str
    name: str
    app_id: str | None = None
    description: str | None = None


class RoleAssign(BaseModel):
    user_id: int
    role_id: str


class RoleNodesUpdate(BaseModel):
    nodes: list[str]


class ModuleToggle(BaseModel):
    enabled: bool


@router.get("/users")
def api_list_users(
    request: Request,
    q: str | None = None,
    team_id: int | None = None,
) -> dict[str, Any]:
    user = require_user(request)
    with session_scope() as session:
        return base_domain.list_users(
            session, ctx_of(user), q=q, team_id=team_id, limit=200
        )


@router.post("/users")
def api_create_user(request: Request, body: UserCreate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            data = body.model_dump(exclude_unset=True)
            kwargs: dict[str, Any] = {
                "username": body.username,
                "realname": body.realname,
                "email": body.email,
                "password": body.password,
            }
            if "team_id" in data:
                kwargs["team_id"] = data["team_id"]
            row = base_domain.create_user(session, ctx_of(user), **kwargs)
        return {"ok": True, "user": row}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.patch("/users/{user_id}")
def api_update_user(request: Request, user_id: int, body: UserUpdate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            kwargs: dict[str, Any] = {
                "user_id": user_id,
                "realname": body.realname,
                "email": body.email,
                "active": body.active,
                "password": body.password,
            }
            data = body.model_dump(exclude_unset=True)
            if "team_id" in data:
                kwargs["team_id"] = data["team_id"]
            row = base_domain.update_user(session, ctx_of(user), **kwargs)
        return {"ok": True, "user": row}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.delete("/users/{user_id}")
def api_delete_user(request: Request, user_id: int) -> dict[str, Any]:
    from modoor.core.errors import AppError

    user = require_user(request)
    if user.id == user_id:
        raise http_error(AppError("validation_error", "cannot delete the current user"))
    try:
        with session_scope() as session:
            base_domain.delete_user(session, ctx_of(user), user_id=user_id)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.get("/teams/tree")
def api_team_tree(request: Request) -> dict[str, Any]:
    user = require_user(request)
    with session_scope() as session:
        return base_domain.list_team_tree(session, ctx_of(user))


@router.post("/teams")
def api_create_team(request: Request, body: TeamCreate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            row = base_domain.create_team(
                session, ctx_of(user), name=body.name, parent=body.parent
            )
        return {"ok": True, "team": row}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.patch("/teams/{team_id}")
def api_update_team(request: Request, team_id: int, body: TeamUpdate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            data = body.model_dump(exclude_unset=True)
            kwargs: dict[str, Any] = {"team_id": team_id}
            if "name" in data:
                kwargs["name"] = data["name"]
            if "active" in data:
                kwargs["active"] = data["active"]
            if "parent" in data:
                kwargs["parent"] = data["parent"]
            row = base_domain.update_team(session, ctx_of(user), **kwargs)
        return {"ok": True, "team": row}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.delete("/teams/{team_id}")
def api_delete_team(request: Request, team_id: int) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            base_domain.delete_team(session, ctx_of(user), team_id=team_id)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.get("/roles")
def api_roles_bundle(request: Request) -> dict[str, Any]:
    user = require_user(request)
    ctx = ctx_of(user)
    with session_scope() as session:
        roles = base_domain.list_roles(session, ctx, limit=200)["items"]
        users = base_domain.list_users(session, ctx, limit=200)["items"]
        apps = base_domain.list_apps(session, ctx, limit=200)["items"]
        assignments = {
            u["id"]: base_domain.list_user_roles(session, ctx, user_id=u["id"])["roles"]
            for u in users
        }
        role_nodes = {
            r["id"]: base_domain.list_role_nodes(session, ctx, role_id=r["id"])["nodes"]
            for r in roles
        }
    catalog = base_domain.list_ability_catalog()
    return {
        "roles": roles,
        "users": users,
        "apps": apps,
        "assignments": assignments,
        "role_nodes": role_nodes,
        "ability_catalog": catalog,
    }


@router.get("/roles/{role_id}/nodes")
def api_get_role_nodes(request: Request, role_id: str) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return base_domain.list_role_nodes(session, ctx_of(user), role_id=role_id)
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.put("/roles/{role_id}/nodes")
def api_set_role_nodes(request: Request, role_id: str, body: RoleNodesUpdate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return base_domain.set_role_nodes(
                session, ctx_of(user), role_id=role_id, nodes=body.nodes
            )
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/roles")
def api_create_role(request: Request, body: RoleCreate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            row = base_domain.create_role(
                session,
                ctx_of(user),
                code=body.code,
                name=body.name,
                app_id=body.app_id,
                description=body.description,
            )
        return {"ok": True, "role": row}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.delete("/roles/{role_id}")
def api_delete_role(request: Request, role_id: str) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            base_domain.delete_role(session, ctx_of(user), role_id=role_id)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/roles/assign")
def api_assign_role(request: Request, body: RoleAssign) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            base_domain.assign_role(
                session, ctx_of(user), user_id=body.user_id, role_id=body.role_id
            )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/roles/revoke")
def api_revoke_role(request: Request, body: RoleAssign) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            base_domain.revoke_role(
                session, ctx_of(user), user_id=body.user_id, role_id=body.role_id
            )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.get("/modules")
def api_list_modules(request: Request) -> dict[str, Any]:
    require_user(request)
    clear_ui_cache()
    with session_scope() as session:
        sync_discovered_modules(session, kit().tenant())
        modules = list_modules(session, kit().tenant())
    return {"modules": modules}


@router.post("/modules/{module_id}/toggle")
def api_toggle_module(request: Request, module_id: str, body: ModuleToggle) -> dict[str, Any]:
    require_user(request)
    try:
        with session_scope() as session:
            set_module_enabled(session, kit().tenant(), module_id, body.enabled)
        clear_ui_cache()
        return {"ok": True, "module_id": module_id, "enabled": body.enabled}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


def register(app, _kit) -> None:
    app.include_router(router)
