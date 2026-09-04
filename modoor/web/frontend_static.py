"""Mount built module webui/dist under /web{base} (SPA fallback)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from modoor.core.settings import get_settings
from modoor.web.mount import WEBUI_MOUNT_PREFIX, join_web_mount
from modoor.web.nav import get_ui_catalog

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side routes under the mount."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def _module_ids_from_env(raw: str) -> list[str] | None:
    """MODOOR_WEBUI_STATIC_MODULES=base,wiki → filter; empty → all with dist."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    return parts or None


def register_frontend_statics(
    app: FastAPI,
    *,
    module_ids: list[str] | None = None,
    skip_prefixes: set[str] | None = None,
) -> list[str]:
    """Mount ``modules/<id>/webui/dist`` at public ``/web`` + ``ui-web.base``.

    Skips modules already covered by reverse-proxy prefixes (dev HMR).
    """
    settings = get_settings()
    root = Path(settings.modoor_modules_root)
    catalog = get_ui_catalog()
    wanted = module_ids if module_ids is not None else _module_ids_from_env(
        getattr(settings, "modoor_webui_static_modules", "") or ""
    )
    skip = skip_prefixes or set()
    registered: list[str] = []

    for mid, meta in catalog.items():
        if wanted is not None and mid not in wanted:
            continue
        base = (meta.get("base") or f"/{mid}").rstrip("/") or f"/{mid}"
        public = join_web_mount(base).rstrip("/")
        if public in skip or any(public.startswith(f"{p}/") for p in skip):
            continue
        dist = root / mid / "webui" / "dist"
        if not dist.is_dir() or not (dist / "index.html").is_file():
            continue
        app.mount(
            public,
            SPAStaticFiles(directory=str(dist), html=True),
            name=f"webui-static-{mid}",
        )
        registered.append(f"{public} → {dist}")
        logger.info("frontend static %s → %s", public, dist)

    if registered:
        logger.info("frontend static mount root %s (%d apps)", WEBUI_MOUNT_PREFIX, len(registered))
    return registered
