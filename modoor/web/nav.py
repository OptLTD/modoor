"""Load PC shell menus from module manifests + live external registry."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from modoor.core.settings import get_settings
from modoor.platform.module_state import discover_manifests
from modoor.platform.services import get_by_module, get_entry_url, list_services
from modoor.platform.manifest_i18n import APP_LABEL_KEY, normalize_manifest_i18n

# re-export for callers / tests
__all__ = ["APP_LABEL_KEY"]


def _load_ui_catalog() -> dict[str, dict[str, Any]]:
    """In-repo modules only (modules/*/module.yaml). External apps come from registry."""
    catalog: dict[str, dict[str, Any]] = {}
    for meta in discover_manifests(get_settings()):
        mid = meta["id"]
        path = Path(meta["path"]) / "module.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        ui = data.get("ui-web") or {}
        exports = data.get("exports") or {}
        top_i18n = meta.get("i18n") or normalize_manifest_i18n(data.get("i18n"))
        kind = (ui.get("kind") or "app").strip()
        # External apps must register at runtime — do not load from modules/
        if kind == "external":
            continue
        menus = list(exports.get("menus") or [])
        menus.sort(key=lambda m: (m.get("sequence", 100), m.get("label") or ""))
        home = ui.get("entry") or (menus[0]["path"] if menus else f"/{mid}")
        # SPA-relative path (no host); external keeps absolute entry URL
        home_path = home if not str(home).startswith("http") else ""
        prefix = ui.get("base") or f"/{mid}"
        catalog[mid] = {
            "id": mid,
            "label": ui.get("label") or mid.title(),
            "i18n": top_i18n,
            "kind": kind,
            "home": home,
            "home_path": home_path,
            "entry": home,
            "base": prefix,
            "recommends": list(ui.get("recommends") or []),
            "source": "module",
            "menus": [
                {
                    "id": m.get("id") or f"{mid}.{i}",
                    "label": m.get("label") or m.get("id") or "Menu",
                    "path": m["path"],
                    "sequence": m.get("sequence", 100),
                }
                for i, m in enumerate(menus)
                if m.get("path")
            ],
        }
    return catalog


def clear_ui_cache() -> None:
    get_ui_catalog.cache_clear()


@lru_cache
def get_ui_catalog() -> dict[str, dict[str, Any]]:
    return _load_ui_catalog()


def modoor_base_url() -> str:
    settings = get_settings()
    return f"http://{settings.modoor_web_host}:{settings.modoor_web_port}"


def meta_from_service(rec: Any) -> dict[str, Any]:
    mfest = rec.manifest or {}
    ui = mfest.get("ui-web") or {}
    top_i18n = normalize_manifest_i18n(mfest.get("i18n"))
    return {
        "id": rec.module_id,
        "label": rec.app_name or ui.get("label") or rec.module_id,
        "i18n": top_i18n,
        "kind": "external",
        "entry": rec.entry_url,
        "home": rec.entry_url,
        "base": "",
        "recommends": list(ui.get("recommends") or ["module_switcher", "logout"]),
        "source": "external",
        "menus": [],
        "exports": rec.exports,
        "service_id": rec.service_id,
    }


def get_module_meta(module_id: str) -> dict[str, Any]:
    """Resolve in-repo catalog first, then live external registry."""
    cat = get_ui_catalog().get(module_id)
    if cat:
        return cat
    rec = get_by_module(module_id)
    if rec:
        return meta_from_service(rec)
    return {}


def resolve_home(module_id: str, meta: dict[str, Any] | None = None) -> str:
    meta = meta or get_module_meta(module_id)
    if meta.get("kind") == "external" or meta.get("source") == "external":
        live = get_entry_url(module_id)
        if live:
            return live

    from modoor.web.entry import call_resolve_entry, entry_launch_href

    resolved = call_resolve_entry(module_id)
    if resolved is not None:
        href = entry_launch_href(resolved, shell_base=modoor_base_url())
        if href:
            return href

    return meta.get("home") or meta.get("entry") or f"/{module_id}"


def module_home(module_id: str) -> str:
    return resolve_home(module_id)


def module_menus(module_id: str) -> list[dict[str, str]]:
    return list(get_module_meta(module_id).get("menus") or [])


def detect_module(path: str) -> str | None:
    from modoor.web.mount import strip_web_mount

    catalog = get_ui_catalog()
    local = strip_web_mount(path)
    best: str | None = None
    best_len = -1
    for mid, meta in catalog.items():
        prefix = meta.get("base") or f"/{mid}"
        if not prefix:
            continue
        if local == prefix or local.startswith(prefix + "/"):
            if len(prefix) > best_len:
                best = mid
                best_len = len(prefix)
    return best


def profile_dict(user: Any | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "realname": user.realname,
        "email": user.email,
        "team_id": user.team_id,
        "tenant": user.tenant,
        "current": user.current,
    }


def switcher_items(
    enabled: set[str],
    *,
    allowed_modules: set[str] | None = None,
) -> list[dict[str, Any]]:
    """In-repo enabled modules + live-registered external apps.

    When ``allowed_modules`` is set, only those module ids are returned (ability filter).
    ``None`` means unrestricted / no ability filter.
    """
    from modoor.web.mount import join_web_mount

    catalog = get_ui_catalog()
    api_base = modoor_base_url()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    order = ["base"] + sorted(m for m in catalog if m != "base")
    for mid in order:
        if mid not in catalog:
            continue
        if mid not in enabled and mid != "base":
            continue
        if allowed_modules is not None and mid not in allowed_modules:
            continue
        meta = catalog[mid]
        if not meta.get("menus") and not meta.get("home") and not meta.get("entry"):
            continue
        home = resolve_home(mid, meta)
        local_home = meta.get("home_path") or meta.get("base") or f"/{mid}"
        if str(home).startswith("http"):
            from urllib.parse import urlparse

            parsed = urlparse(home)
            path = parsed.path or join_web_mount(local_home)
            href = home
        else:
            path = join_web_mount(str(home) or local_home)
            href = f"{api_base}{path}"
        menus = [
            {**m, "path": join_web_mount(m["path"])}
            for m in (meta.get("menus") or [])
            if m.get("path")
        ]
        items.append(
            {
                "id": mid,
                "label": meta["label"],
                "i18n": meta.get("i18n") or {},
                "path": path,
                "href": href,
                "kind": meta.get("kind") or "app",
                "online": True,
                "entry": href,
                "menus": menus,
                "exports": None,
                "exports_count": None,
                "source": "module",
            }
        )
        seen.add(mid)

    for svc in list_services():
        mid = svc.get("module_id") or svc.get("service_id")
        if not mid or mid in seen:
            continue
        if allowed_modules is not None and mid not in allowed_modules:
            continue
        href = f"{api_base}/go/{mid}"
        exports = (svc.get("manifest") or {}).get("exports") or {}
        arts = svc.get("artifacts") or {}
        items.append(
            {
                "id": mid,
                "label": svc.get("app_name") or mid,
                "href": href,
                "kind": "external",
                "online": True,
                "entry": svc.get("entry_url"),
                "exports": exports,
                "exports_count": {
                    "tools": len(exports.get("tools") or []),
                    "skills": len(exports.get("skills") or []),
                    "models": len(arts.get("models") or []),
                },
                "source": "external",
            }
        )
        seen.add(mid)

    return items


def registry_catalog(
    enabled: set[str],
    *,
    user: Any | None = None,
    allowed_modules: set[str] | None = None,
) -> dict[str, Any]:
    """Catalog: tenant + profile + modules + aggregated MODULE_CONTRACT exports."""
    from modoor.platform.services import aggregated_exports

    settings = get_settings()
    base = modoor_base_url()
    tenant_id = getattr(user, "tenant", None)
    tenant_name = settings.modoor_tenant
    if tenant_id is not None:
        from modoor.core.db import session_scope
        from platform.base.domain import SystemTenant

        with session_scope() as session:
            row = session.get(SystemTenant, int(tenant_id))
            if row is not None:
                tenant_name = row.name
    else:
        from modoor.core.db import session_scope
        from platform.base.domain import ensure_tenant

        with session_scope() as session:
            tenant_id = int(
                ensure_tenant(
                    session, tenant_name, tenant_id=settings.modoor_tenant_id
                )["tenant"]["id"]
            )
    return {
        "tenant": {
            "id": tenant_id,
            "name": tenant_name,
        },
        "profile": profile_dict(user),
        "modoor_url": base,
        "logout_url": f"{base}/logout",
        "modules": switcher_items(enabled, allowed_modules=allowed_modules),
        "exports": aggregated_exports(),
    }
