"""HTTP: /api/record/* + /api/auth/* for Vue shell."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from modoor.core.ctx import Ctx
from modoor.core.db import session_scope
from modoor.core.errors import AppError
from modoor.core.settings import get_settings
from modoor.engine.service import get_engine
from modules.base import domain as base_domain
from modules.base.domain import SystemUser

router = APIRouter()


def _tenant_id() -> int:
    from modules.base.domain import ensure_tenant

    with session_scope() as session:
        return int(ensure_tenant(session, get_settings().modoor_tenant)["tenant"]["id"])


def _user_from_session(request: Request) -> SystemUser | None:
    uid = request.session.get("user_id")
    if uid is None or uid == "":
        return None
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        request.session.pop("user_id", None)
        return None
    with session_scope() as session:
        user = base_domain.load_user(session, user_id, tenant=_tenant_id())
        if user is None or not user.active:
            return None
        _ = (user.username, user.realname, user.current)
        if user.login is not None:
            session.expunge(user.login)
        session.expunge(user)
        return user


def _require_user(request: Request) -> SystemUser:
    user = _user_from_session(request)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    return user


def _ctx(user: SystemUser) -> Ctx:
    return Ctx(tenant=user.tenant, user_id=user.id, team_id=user.team_id)


def _err(exc: Exception) -> HTTPException:
    if isinstance(exc, AppError):
        code = 404 if exc.code == "not_found" else 400
        return HTTPException(status_code=code, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, KeyError):
        return HTTPException(status_code=400, detail={"code": "not_found", "message": str(exc)})
    return HTTPException(status_code=500, detail={"code": "internal", "message": str(exc)})


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
def api_login(request: Request, body: LoginBody) -> dict[str, Any]:
    try:
        with session_scope() as session:
            user = base_domain.authenticate_user(
                session,
                tenant=_tenant_id(),
                username=body.username,
                password=body.password,
            )
            request.session["user_id"] = user.id
            return {
                "ok": True,
                "user": {
                    "id": user.id,
                    "uukey": user.uukey,
                    "username": user.username,
                    "realname": user.realname,
                    "tenant": user.tenant,
                    "current": user.current,
                },
            }
    except AppError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


@router.get("/api/auth/me")
def api_me(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    return {
        "user": {
            "id": user.id,
            "uukey": user.uukey,
            "username": user.username,
            "realname": user.realname,
            "tenant": user.tenant,
            "current": user.current,
        }
    }


@router.post("/api/auth/logout")
def api_logout(request: Request) -> dict[str, Any]:
    request.session.clear()
    return {"ok": True}


@router.post("/api/record/schema")
def api_schema(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> Any:
    _require_user(request)
    try:
        return get_engine().table_schema(body)
    except Exception as exc:  # noqa: BLE001
        raise _err(exc) from exc


@router.post("/api/record/input")
def api_input(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> Any:
    user = _require_user(request)
    try:
        with session_scope() as session:
            return get_engine().input_schema(session, _ctx(user), body)
    except Exception as exc:  # noqa: BLE001
        raise _err(exc) from exc


@router.post("/api/record/search")
def api_search(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> Any:
    user = _require_user(request)
    try:
        with session_scope() as session:
            return get_engine().search(session, _ctx(user), body)
    except Exception as exc:  # noqa: BLE001
        raise _err(exc) from exc


@router.post("/api/record/upsert")
def api_upsert(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> Any:
    user = _require_user(request)
    try:
        with session_scope() as session:
            return get_engine().upsert(session, _ctx(user), body)
    except Exception as exc:  # noqa: BLE001
        raise _err(exc) from exc


@router.post("/api/record/delete")
def api_delete(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> Any:
    user = _require_user(request)
    model = str(body.get("model") or "").strip()
    keys = body.get("keys") or []
    if not model or not isinstance(keys, list):
        raise HTTPException(status_code=400, detail="model and keys required")
    try:
        with session_scope() as session:
            return get_engine().delete(session, _ctx(user), model=model, keys=[str(k) for k in keys])
    except Exception as exc:  # noqa: BLE001
        raise _err(exc) from exc
