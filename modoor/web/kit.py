"""PC Shell kit passed to modules/*/ui/web.py register(app, kit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from modoor.core.ctx import Ctx
from modoor.core.db import session_scope
from modoor.core.settings import get_settings
from modoor.platform.module_state import enabled_module_ids
from modoor.web.nav import (
    detect_module,
    get_module_meta,
    module_menus,
    switcher_items,
)
from modules.base import domain as base_domain
from modules.base.domain import SystemUser

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ShellKit:
    """Shared shell helpers for template modules (auth, render, flash, tenant)."""

    def __init__(self, jinja: Jinja2Templates | None = None) -> None:
        self.templates = jinja or templates

    def settings(self):
        return get_settings()

    def tenant_name(self) -> str:
        return self.settings().modoor_tenant

    def tenant(self) -> int:
        """Resolved tenant id (ensures tenant + root team exist)."""
        from modules.base.domain import ensure_tenant

        with session_scope() as session:
            return int(ensure_tenant(session, self.tenant_name())["tenant"]["id"])

    def current_user(self, request: Request) -> SystemUser | None:
        uid = request.session.get("user_id")
        if uid is None or uid == "":
            return None
        try:
            user_id = int(uid)
        except (TypeError, ValueError):
            request.session.pop("user_id", None)
            return None
        with session_scope() as session:
            user = base_domain.load_user(session, user_id, tenant=self.tenant())
            if user is None or not user.active:
                return None
            _ = (user.username, user.realname, user.current)
            if user.login is not None:
                session.expunge(user.login)
            session.expunge(user)
            return user

    def require_user(self, request: Request) -> SystemUser:
        user = self.current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="login required")
        return user

    def ctx(self, user: SystemUser) -> Ctx:
        return Ctx(tenant=user.tenant, user_id=user.id, team_id=user.team_id)

    def enabled(self, session) -> set[str]:
        return enabled_module_ids(session, self.tenant())

    def user_initials(self, user: SystemUser | None) -> str:
        if user is None:
            return "?"
        name = (user.realname or user.username or "?").strip()
        parts = [p for p in name.replace("_", " ").split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()

    def flash(self, request: Request, message: str) -> None:
        request.session["flash"] = message

    def login_redirect(self) -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    def render(
        self,
        request: Request,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
    ):
        ctx = dict(context or {})
        user = self.current_user(request)
        with session_scope() as session:
            enabled = self.enabled(session)
        current_module = detect_module(request.url.path) or request.session.get(
            "active_module"
        )
        if current_module and current_module not in enabled and current_module != "base":
            current_module = "base"
        if current_module:
            request.session["active_module"] = current_module
        current_label = "Modoor"
        meta = get_module_meta(current_module) if current_module else {}
        if meta.get("label"):
            current_label = meta["label"]
        else:
            for item in switcher_items(enabled):
                if item["id"] == current_module:
                    current_label = item["label"]
                    break
        ctx.update(
            {
                "request": request,
                "current_user": user,
                "user_initials": self.user_initials(user),
                "tenant": self.tenant_name(),
                "tenant_id": self.tenant(),
                "flash": request.session.pop("flash", None),
                "enabled_modules": enabled,
                "current_module": current_module,
                "current_module_label": current_label,
                "module_switcher": switcher_items(enabled),
                "module_menus": module_menus(current_module) if current_module else [],
                "inbox_messages": [],
            }
        )
        return self.templates.TemplateResponse(request, name, ctx, status_code=status_code)


_kit: ShellKit | None = None


def get_kit() -> ShellKit:
    global _kit
    if _kit is None:
        _kit = ShellKit()
    return _kit
