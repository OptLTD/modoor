"""PC web console shell — auth, registry, health; module routes via ui/web.py."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from modoor.platform.bootstrap import bootstrap
from modoor.core.db import init_db, session_scope
from modoor.core.errors import AppError
from modoor.engine.api import router as engine_router
from modoor.platform.loader import register_module_web
from modoor.platform import services as service_registry
from modoor.platform.tickets import issue_ticket, verify_ticket
from modoor.core.settings import get_settings
from modoor.web.frontend import register_frontends
from modoor.web.kit import get_kit
from modoor.web.nav import (
    clear_ui_cache,
    get_module_meta,
    registry_catalog,
    resolve_home,
)
from modules.base import domain as base_domain


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings.cache_clear()
    clear_ui_cache()
    init_db()
    bootstrap()
    from modoor.runtime.worker import start_inprocess, stop_inprocess

    start_inprocess()
    try:
        yield
    finally:
        stop_inprocess()


app = FastAPI(title="Modoor Console", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().modoor_session_secret,
    session_cookie="modoor_session",
    same_site="lax",
    https_only=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:5176",
        "http://localhost:5176",
        "http://127.0.0.1:5177",
        "http://localhost:5177",
        "http://127.0.0.1:5178",
        "http://localhost:5178",
        "http://127.0.0.1:5179",
        "http://localhost:5179",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(engine_router)

_LOGO_PNG = Path(__file__).resolve().parents[2] / "logo.png"

kit = get_kit()
register_module_web(app, kit)
register_frontends(app)


# ---- Auth / home / health ----

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    next_url = request.query_params.get("next") or ""
    user = kit.current_user(request)
    if user:
        with session_scope() as session:
            mid, href = kit.landing_for_user(session, user, next_url=next_url)
            if mid:
                request.session["active_module"] = mid
            else:
                request.session.pop("active_module", None)
        return RedirectResponse(href, status_code=303)
    return kit.render(
        request,
        "login.html",
        {"username": "admin", "next": next_url, "error": None},
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
):
    try:
        with session_scope() as session:
            user = base_domain.authenticate_user(
                session,
                tenant=kit.tenant(),
                username=username,
                password=password,
                allow_fallback=True,
            )
            request.session["user_id"] = user.id
            request.session["username"] = user.username
            mid, href = kit.landing_for_user(session, user, next_url=next)
            if mid:
                request.session["active_module"] = mid
            else:
                request.session.pop("active_module", None)
    except AppError as exc:
        return kit.render(
            request,
            "login.html",
            {"error": exc.message, "username": username, "next": next},
            status_code=400,
        )
    return RedirectResponse(href, status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = kit.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    request.session.pop("active_module", None)
    with session_scope() as session:
        apps = kit.workbench_apps(session, user)
    return kit.render(request, "home.html", {"apps": apps})


@app.get("/logout")
@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    accept = request.headers.get("accept") or ""
    if "application/json" in accept:
        return {"ok": True}
    return RedirectResponse("/login", status_code=303)


@app.get("/logo.png", include_in_schema=False)
def logo_png():
    if not _LOGO_PNG.is_file():
        raise HTTPException(status_code=404, detail="logo not found")
    return FileResponse(_LOGO_PNG, media_type="image/png")


@app.get("/health")
def health():
    s = kit.settings()
    return {
        "status": "ok",
        "tenant": s.modoor_tenant,
        "database": s.database_url.split("@")[-1]
        if "@" in s.database_url
        else s.database_url,
        "registered_services": len(service_registry.list_services()),
    }


# ---- External app registry (Modoor as hub) ----


class RegistryServiceIn(BaseModel):
    service_id: str
    module_id: str
    app_name: str = ""
    entry_url: str
    health_url: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class HeartbeatIn(BaseModel):
    entry_url: str | None = None
    manifest: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None


class ManifestArtifactsIn(BaseModel):
    manifest: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None


def _require_api_key(request: Request) -> None:
    auth = request.headers.get("Authorization") or ""
    key = request.headers.get("X-API-Key") or ""
    if auth.lower().startswith("bearer "):
        key = key or auth[7:].strip()
    if key != kit.settings().modoor_api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


def _user_from_ticket(token: str | None):
    payload = verify_ticket(token or "")
    if not payload:
        return None
    with session_scope() as session:
        user = base_domain.load_user(session, payload["user_id"], tenant=payload["tenant"])
        if user is None or not user.active:
            return None
        if user.tenant != kit.tenant():
            return None
        session.expunge(user)
        return user


def asdict_service(rec) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(rec)


@app.get("/api/registry/catalog")
def api_registry_catalog(request: Request):
    ticket = request.headers.get("X-Modoor-Ticket") or request.query_params.get("ticket")
    user = kit.current_user(request) or _user_from_ticket(ticket)
    tenant = int(user.tenant) if user is not None else kit.tenant()
    with session_scope() as session:
        enabled = kit.enabled(session, tenant)
        allowed = None
        if user is not None:
            from modoor.platform.services import list_services

            extra = {
                str(svc.get("module_id") or svc.get("service_id") or "")
                for svc in list_services()
            }
            extra.discard("")
            allowed = base_domain.allowed_modules_for_user(
                session,
                kit.ctx(user),
                user_id=user.id,
                enabled=enabled,
                extra_module_ids=extra,
            )
    return registry_catalog(enabled, user=user, allowed_modules=allowed)


@app.get("/api/shell/modules")
def api_shell_modules(request: Request):
    user = kit.require_user(request)
    with session_scope() as session:
        enabled = kit.enabled(session, user.tenant)
        allowed = kit.allowed_modules_for(session, user, enabled)
    return registry_catalog(enabled, user=user, allowed_modules=allowed)


@app.post("/auth/switch")
def switch_tenant_form(request: Request, tenant_id: int = Form(...)):
    user = kit.require_user(request)
    with session_scope() as session:
        switched = base_domain.switch_login_tenant(
            session, base_id=user.base_id, tenant_id=int(tenant_id)
        )
        request.session["user_id"] = switched.id
        mid, href = kit.landing_for_user(session, switched)
        if mid:
            request.session["active_module"] = mid
        else:
            request.session.pop("active_module", None)
    return RedirectResponse(href, status_code=303)


@app.get("/go/{module_id}")
def launch_module(request: Request, module_id: str):
    user = kit.require_user(request)
    meta = get_module_meta(module_id)
    if not meta:
        raise HTTPException(status_code=404, detail="module not found")

    with session_scope() as session:
        enabled = kit.enabled(session, user.tenant)
        if meta.get("source") != "external":
            if module_id not in enabled and module_id != "base":
                raise HTTPException(status_code=404, detail="module disabled")
        from modoor.platform.services import list_services

        extra = {
            str(svc.get("module_id") or svc.get("service_id") or "")
            for svc in list_services()
        }
        extra.discard("")
        allowed = base_domain.allowed_modules_for_user(
            session,
            kit.ctx(user),
            user_id=user.id,
            enabled=enabled,
            extra_module_ids=extra,
        )
        if allowed is not None and module_id not in allowed:
            raise HTTPException(status_code=403, detail="module not permitted")

    target = resolve_home(module_id, meta)
    if meta.get("kind") == "external" or meta.get("source") == "external":
        if not target or not str(target).startswith("http"):
            raise HTTPException(status_code=503, detail="external app offline")
        ticket = issue_ticket(user_id=user.id, tenant=user.tenant)
        sep = "&" if "?" in target else "?"
        target = f"{target}{sep}modoor_ticket={ticket}"
    request.session["active_module"] = module_id
    return RedirectResponse(target, status_code=303)


@app.get("/api/registry/services")
def api_registry_list(request: Request):
    _require_api_key(request)
    return {"items": service_registry.list_services()}


@app.post("/api/registry/services")
def api_registry_register(request: Request, body: RegistryServiceIn):
    _require_api_key(request)
    try:
        rec = service_registry.register_service(
            service_id=body.service_id,
            module_id=body.module_id,
            app_name=body.app_name or body.module_id,
            entry_url=body.entry_url,
            health_url=body.health_url,
            meta=body.meta,
            manifest=body.manifest or None,
            artifacts=body.artifacts or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "service": asdict_service(rec)}


@app.put("/api/registry/services/{service_id}/manifest")
def api_registry_set_manifest(
    request: Request, service_id: str, body: ManifestArtifactsIn
):
    _require_api_key(request)
    rec = service_registry.set_manifest_artifacts(
        service_id,
        manifest=body.manifest,
        artifacts=body.artifacts,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="service not registered")
    return {"ok": True, "service": asdict_service(rec)}


@app.get("/api/registry/exports")
def api_registry_exports():
    return service_registry.aggregated_exports()


@app.post("/api/registry/services/{service_id}/heartbeat")
def api_registry_heartbeat(request: Request, service_id: str, body: HeartbeatIn):
    _require_api_key(request)
    rec = service_registry.heartbeat(
        service_id,
        entry_url=body.entry_url,
        manifest=body.manifest,
        artifacts=body.artifacts,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="service not registered")
    return {"ok": True, "service": asdict_service(rec)}


@app.delete("/api/registry/services/{service_id}")
def api_registry_delete(request: Request, service_id: str):
    _require_api_key(request)
    ok = service_registry.unregister_service(service_id)
    if not ok:
        raise HTTPException(status_code=404, detail="service not registered")
    return {"ok": True}


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "modoor.web.app:app",
        host=settings.modoor_web_host,
        port=settings.modoor_web_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
