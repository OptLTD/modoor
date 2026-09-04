"""Discover and load business modules (domain / MCP tools / PC web UI)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from modoor.platform.module_state import ALWAYS_ON, discover_manifests, enabled_module_ids
from modoor.core.settings import Settings, get_settings


def _module_ids(settings: Settings) -> list[str]:
    return [m["id"] for m in discover_manifests(settings)]


def load_module_domains(settings: Settings | None = None) -> list[str]:
    """Import modules.<id>.domain so Base.metadata sees their tables.

    Domain models always load (schema), regardless of enable flag.
    """
    settings = settings or get_settings()
    root = Path(settings.modoor_modules_root)
    loaded: list[str] = []
    for module_id in _module_ids(settings):
        domain_file = root / module_id / "domain.py"
        if not domain_file.is_file():
            continue
        dotted = f"modules.{module_id}.domain"
        importlib.import_module(dotted)
        loaded.append(dotted)
    return loaded


def register_module_tools(mcp: Any, settings: Settings | None = None) -> list[str]:
    """Register MCP tools only for enabled modules (base always on)."""
    settings = settings or get_settings()
    root = Path(settings.modoor_modules_root)

    enabled: set[str] | None = None
    try:
        from modoor.core.db import session_scope

        with session_scope() as session:
            from modules.base.domain import ensure_tenant

            tenant_id = int(
                ensure_tenant(
                    session,
                    settings.modoor_tenant,
                    tenant_id=settings.modoor_tenant_id,
                )["tenant"]["id"]
            )
            enabled = enabled_module_ids(session, tenant_id)
    except Exception:  # noqa: BLE001
        enabled = set(_module_ids(settings)) | set(ALWAYS_ON)

    registered: list[str] = []
    for module_id in _module_ids(settings):
        if enabled is not None and module_id not in enabled:
            continue
        tools_init = root / module_id / "tools" / "__init__.py"
        if not tools_init.is_file():
            continue
        dotted = f"modules.{module_id}.tools"
        mod = importlib.import_module(dotted)
        register = getattr(mod, "register", None)
        if register is None:
            continue
        register(mcp)
        registered.append(dotted)
    return registered


def register_module_web(app: Any, kit: Any, settings: Settings | None = None) -> list[str]:
    """Call modules.<id>.webui.register(app, kit).

    Routes always register so disabled modules can still 303 to base with flash.
    Enable checks stay inside each module's handlers.
    """
    settings = settings or get_settings()
    root = Path(settings.modoor_modules_root)
    registered: list[str] = []
    for module_id in _module_ids(settings):
        candidates = [
            (root / module_id / "webui.py", f"modules.{module_id}.webui"),
            (root / module_id / "web.py", f"modules.{module_id}.web"),
            (root / module_id / "ui" / "web.py", f"modules.{module_id}.ui.web"),
        ]
        dotted: str | None = None
        for path, name in candidates:
            if path.is_file():
                dotted = name
                break
        if dotted is None:
            continue
        mod = importlib.import_module(dotted)
        register = getattr(mod, "register", None)
        if register is None:
            continue
        register(app, kit)
        registered.append(dotted)
    return registered
