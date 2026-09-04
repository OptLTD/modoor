"""Persisted module install / enable state (per tenant)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import yaml
from sqlalchemy import Integer, Boolean, DateTime, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.db import Base
from modoor.core.errors import AppError
from modoor.core.settings import Settings, get_settings
from modoor.platform.manifest_i18n import normalize_manifest_i18n

ALWAYS_ON = frozenset({"base"})


class ModuleInstall(Base):
    __tablename__ = "module_install"
    __table_args__ = (
        UniqueConstraint("tenant", "module_id", name="uq_module_install_tenant_module"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    module_id: Mapped[str] = mapped_column(String(64), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def discover_manifests(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    root = settings.modoor_modules_root
    items: list[dict[str, Any]] = []
    if not root.is_dir():
        return items
    for path in sorted(root.glob("*/module.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mid = data.get("id") or path.parent.name
        ui = data.get("ui-web") or {}
        if not isinstance(ui, dict):
            ui = {}
        kind = str(ui.get("kind") or "app")
        label = str(ui.get("label") or mid)
        raw_tags = data.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        # 派生标签：便于筛选
        derived = [kind, str(data.get("risk_default") or "").strip()]
        for t in derived:
            if t and t not in tags:
                tags.append(t)
        items.append(
            {
                "id": mid,
                "label": label,
                "kind": kind,
                "version": str(data.get("version") or ""),
                "summary": data.get("summary") or "",
                "tags": tags,
                "risk_default": data.get("risk_default") or "",
                "ability": [str(x) for x in (data.get("ability") or []) if str(x).strip()],
                "depends": list(data.get("depends") or []),
                "tools": (data.get("exports") or {}).get("tools") or [],
                "skills": (data.get("exports") or {}).get("skills") or [],
                "i18n": normalize_manifest_i18n(data.get("i18n")),
                "path": str(path.parent),
            }
        )
    return items


def sync_discovered_modules(session: Session, tenant: int, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Ensure a ModuleInstall row exists for each on-disk module."""
    settings = settings or get_settings()
    discovered = discover_manifests(settings)
    existing = {
        row.module_id: row
        for row in session.scalars(
            select(ModuleInstall).where(ModuleInstall.tenant == tenant)
        )
    }
    for item in discovered:
        mid = item["id"]
        row = existing.get(mid)
        if row is None:
            row = ModuleInstall(
                id=str(uuid.uuid4()),
                tenant=tenant,
                module_id=mid,
                enabled=True,
                version=item["version"],
            )
            session.add(row)
            existing[mid] = row
        else:
            row.version = item["version"]
            if mid in ALWAYS_ON:
                row.enabled = True
        row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return list_modules(session, tenant, settings=settings)


def list_modules(
    session: Session, tenant: int, settings: Settings | None = None
) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    discovered = {m["id"]: m for m in discover_manifests(settings)}
    rows = {
        r.module_id: r
        for r in session.scalars(
            select(ModuleInstall).where(ModuleInstall.tenant == tenant)
        )
    }
    out: list[dict[str, Any]] = []
    for mid, meta in discovered.items():
        row = rows.get(mid)
        enabled = True if row is None else bool(row.enabled)
        if mid in ALWAYS_ON:
            enabled = True
        out.append(
            {
                **meta,
                "enabled": enabled,
                "always_on": mid in ALWAYS_ON,
                "install_id": row.id if row else None,
                "tags": _module_tags(meta, enabled=enabled, always_on=mid in ALWAYS_ON),
            }
        )
    return out


def _module_tags(meta: dict[str, Any], *, enabled: bool, always_on: bool) -> list[str]:
    tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()]
    status = "enabled" if enabled else "disabled"
    if status not in tags:
        tags.append(status)
    if always_on and "always-on" not in tags:
        tags.append("always-on")
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def enabled_module_ids(session: Session, tenant: int) -> set[str]:
    rows = list(
        session.scalars(select(ModuleInstall).where(ModuleInstall.tenant == tenant))
    )
    if not rows:
        # no rows yet → all discovered modules on
        return {m["id"] for m in discover_manifests()}
    enabled = {r.module_id for r in rows if r.enabled}
    enabled |= ALWAYS_ON
    return enabled


def set_module_enabled(
    session: Session, tenant: int, module_id: str, enabled: bool
) -> dict[str, Any]:
    if module_id in ALWAYS_ON and not enabled:
        raise AppError("validation_error", f"module '{module_id}' cannot be disabled")
    discovered = {m["id"] for m in discover_manifests()}
    if module_id not in discovered:
        raise AppError("not_found", f"module not found: {module_id}")
    row = session.scalar(
        select(ModuleInstall).where(
            ModuleInstall.tenant == tenant,
            ModuleInstall.module_id == module_id,
        )
    )
    if row is None:
        meta = next(m for m in discover_manifests() if m["id"] == module_id)
        row = ModuleInstall(
            id=str(uuid.uuid4()),
            tenant=tenant,
            module_id=module_id,
            enabled=enabled,
            version=meta["version"],
        )
        session.add(row)
    else:
        row.enabled = enabled
        row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return {
        "module_id": module_id,
        "enabled": row.enabled,
        "version": row.version,
    }
