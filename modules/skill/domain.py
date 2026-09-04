from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Integer, DateTime, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError
from modoor.core.settings import get_settings

SOURCE_MODULE = "module"
SOURCE_CUSTOM = "custom"
CUSTOM_MODULE_ID = "custom"


class SkillItem(Base):
    __tablename__ = "skill_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant", "skill_key", name="uq_skill_items_tenant_key"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    skill_key: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, default="")
    when_to_use: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    tools_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmations_json: Mapped[str] = mapped_column(Text, default="[]")
    boundaries: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _normalize_key(skill_key: str) -> str:
    value = skill_key.strip().lower().replace("-", "_").replace(" ", "_")
    if not value:
        raise AppError("validation_error", "skill_key is required")
    if not _KEY_RE.match(value):
        raise AppError(
            "validation_error",
            "skill_key must be lowercase letters/digits/underscore, start with a letter",
        )
    return value


def _loads_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _dumps_list(value: list[Any] | None) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _custom_id(skill_key: str) -> str:
    return f"{CUSTOM_MODULE_ID}.{skill_key}"


def _parse_skill_md(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            loaded = yaml.safe_load(parts[1]) or {}
            if isinstance(loaded, dict):
                meta = loaded
            body = parts[2].lstrip("\n")
    return {**meta, "content": body}


def _render_skill_md(payload: dict[str, Any]) -> str:
    front = {
        "id": payload.get("id"),
        "title": payload.get("title") or "",
        "summary": payload.get("summary") or "",
        "when_to_use": payload.get("when_to_use") or "",
        "tools": payload.get("tools") or [],
        "confirmations": payload.get("confirmations") or [],
    }
    if payload.get("boundaries"):
        front["boundaries"] = payload["boundaries"]
    body = (payload.get("content") or "").strip()
    dumped = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{dumped}\n---\n\n{body}\n"


def _custom_to_dict(
    row: SkillItem, *, include_content: bool = True
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": _custom_id(row.skill_key),
        "record_id": row.id,
        "source": SOURCE_CUSTOM,
        "readonly": False,
        "module": CUSTOM_MODULE_ID,
        "skill_key": row.skill_key,
        "title": row.title,
        "summary": row.summary or "",
        "when_to_use": row.when_to_use or "",
        "tools": _loads_list(row.tools_json),
        "confirmations": _loads_list(row.confirmations_json),
        "boundaries": row.boundaries or "",
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "uri": f"skill://{CUSTOM_MODULE_ID}/{row.skill_key}",
    }
    if include_content:
        data["content"] = row.content or ""
        data["markdown"] = _render_skill_md(data)
    return data


def _module_skill_paths() -> list[Path]:
    root = Path(get_settings().modoor_modules_root)
    if not root.is_dir():
        return []
    return sorted(root.glob("*/skills/*.md"))


def _read_module_skill(path: Path) -> dict[str, Any]:
    module_id = path.parent.parent.name
    skill_name = path.stem
    raw = path.read_text(encoding="utf-8")
    parsed = _parse_skill_md(raw)
    skill_id = str(parsed.get("id") or f"{module_id}.{skill_name}")
    return {
        "id": skill_id,
        "source": SOURCE_MODULE,
        "readonly": True,
        "module": module_id,
        "skill_key": skill_name,
        "title": str(parsed.get("title") or skill_name),
        "summary": str(parsed.get("summary") or ""),
        "when_to_use": str(parsed.get("when_to_use") or ""),
        "tools": list(parsed.get("tools") or [])
        if isinstance(parsed.get("tools"), list)
        else [],
        "confirmations": list(parsed.get("confirmations") or [])
        if isinstance(parsed.get("confirmations"), list)
        else [],
        "boundaries": str(parsed.get("boundaries") or ""),
        "content": str(parsed.get("content") or ""),
        "markdown": raw,
        "uri": f"skill://{module_id}/{skill_name}",
        "path": str(path),
        "updated_at": None,
    }


def list_module_skills(*, q: str | None = None) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    items: list[dict[str, Any]] = []
    for path in _module_skill_paths():
        item = _read_module_skill(path)
        # list view: omit heavy body
        slim = {k: v for k, v in item.items() if k not in ("content", "markdown")}
        if needle:
            blob = " ".join(
                [
                    slim.get("id") or "",
                    slim.get("title") or "",
                    slim.get("summary") or "",
                    slim.get("module") or "",
                    slim.get("skill_key") or "",
                ]
            ).lower()
            if needle not in blob:
                continue
        items.append(slim)
    return items


def get_module_skill(
    *, skill_id: str | None = None, module: str | None = None, skill_key: str | None = None
) -> dict[str, Any]:
    if skill_id and "." in skill_id:
        module, skill_key = skill_id.split(".", 1)
    if not module or not skill_key:
        raise AppError("validation_error", "module+skill_key or skill_id is required")
    if module == CUSTOM_MODULE_ID:
        raise AppError("not_found", "Not a module-exported skill")
    path = Path(get_settings().modoor_modules_root) / module / "skills" / f"{skill_key}.md"
    if not path.is_file():
        raise AppError("not_found", f"Module skill not found: {module}.{skill_key}")
    return _read_module_skill(path)


def _scope_query(ctx: Ctx):
    stmt = select(SkillItem).where(SkillItem.tenant == ctx.tenant)
    if ctx.team_id is not None:
        stmt = stmt.where(
            SkillItem.team_id == ctx.team_id
        )
    return stmt


def _get_custom(
    session: Session,
    ctx: Ctx,
    *,
    record_id: str | None = None,
    skill_key: str | None = None,
    skill_id: str | None = None,
) -> SkillItem:
    if skill_id and skill_id.startswith(f"{CUSTOM_MODULE_ID}."):
        skill_key = skill_id.split(".", 1)[1]
    if record_id:
        row = session.get(SkillItem, record_id)
    elif skill_key:
        norm = _normalize_key(skill_key)
        row = session.scalar(
            select(SkillItem).where(
                SkillItem.tenant == ctx.tenant, SkillItem.skill_key == norm
            )
        )
    else:
        raise AppError("validation_error", "record_id, skill_key, or skill_id is required")

    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "Custom skill not found")
    if ctx.team_id is not None and row.team_id is not None and row.team_id != ctx.team_id:
        raise AppError("permission_denied", "Skill outside team scope")
    return row


def list_custom_skills(
    session: Session,
    ctx: Ctx,
    *,
    q: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 200:
        raise AppError("validation_error", "limit must be between 1 and 200")
    stmt = _scope_query(ctx).order_by(SkillItem.updated_at.desc()).limit(limit)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (SkillItem.title.ilike(like))
            | (SkillItem.skill_key.ilike(like))
            | (SkillItem.summary.ilike(like))
        )
    return [
        _custom_to_dict(row, include_content=False) for row in session.scalars(stmt)
    ]


def list_skills(
    session: Session,
    ctx: Ctx,
    *,
    source: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if source is not None and source not in (SOURCE_MODULE, SOURCE_CUSTOM):
        raise AppError("validation_error", "source must be module or custom")
    items: list[dict[str, Any]] = []
    if source in (None, SOURCE_MODULE):
        items.extend(list_module_skills(q=q))
    if source in (None, SOURCE_CUSTOM):
        items.extend(list_custom_skills(session, ctx, q=q, limit=limit))
    return {"items": items, "count": len(items)}


def get_skill(
    session: Session,
    ctx: Ctx,
    *,
    skill_id: str | None = None,
    source: str | None = None,
    module: str | None = None,
    skill_key: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    wants_custom = (
        record_id is not None
        or source == SOURCE_CUSTOM
        or module == CUSTOM_MODULE_ID
        or (skill_id is not None and skill_id.startswith(f"{CUSTOM_MODULE_ID}."))
    )
    wants_module = source == SOURCE_MODULE or (
        module is not None and module != CUSTOM_MODULE_ID
    )

    if wants_custom and not wants_module:
        row = _get_custom(
            session,
            ctx,
            record_id=record_id,
            skill_key=skill_key,
            skill_id=skill_id,
        )
        return _custom_to_dict(row, include_content=True)

    if wants_module and not wants_custom:
        return get_module_skill(skill_id=skill_id, module=module, skill_key=skill_key)

    if skill_id:
        if skill_id.startswith(f"{CUSTOM_MODULE_ID}."):
            return _custom_to_dict(
                _get_custom(session, ctx, skill_id=skill_id), include_content=True
            )
        try:
            return get_module_skill(skill_id=skill_id)
        except AppError as exc:
            if exc.code != "not_found":
                raise
            return _custom_to_dict(
                _get_custom(session, ctx, skill_id=skill_id), include_content=True
            )

    if module and skill_key:
        if module == CUSTOM_MODULE_ID:
            return _custom_to_dict(
                _get_custom(session, ctx, skill_key=skill_key), include_content=True
            )
        return get_module_skill(module=module, skill_key=skill_key)

    if skill_key:
        try:
            return _custom_to_dict(
                _get_custom(session, ctx, skill_key=skill_key), include_content=True
            )
        except AppError as exc:
            if exc.code != "not_found":
                raise

    raise AppError("validation_error", "skill_id or module+skill_key is required")


def create_skill(
    session: Session,
    ctx: Ctx,
    *,
    skill_key: str,
    title: str,
    summary: str = "",
    when_to_use: str = "",
    content: str = "",
    tools: list[Any] | None = None,
    confirmations: list[Any] | None = None,
    boundaries: str = "",
) -> dict[str, Any]:
    norm = _normalize_key(skill_key)
    title = title.strip()
    if not title:
        raise AppError("validation_error", "title is required")

    existing = session.scalar(
        select(SkillItem).where(
            SkillItem.tenant == ctx.tenant, SkillItem.skill_key == norm
        )
    )
    if existing is not None:
        raise AppError(
            "conflict",
            f"skill_key already exists: {norm}",
            details={"skill_key": norm},
        )

    row = SkillItem(
        id=str(uuid.uuid4()),
        tenant=ctx.tenant,
        team_id=ctx.team_id,
        skill_key=norm,
        title=title,
        summary=summary or "",
        when_to_use=when_to_use or "",
        content=content or "",
        tools_json=_dumps_list(tools),
        confirmations_json=_dumps_list(confirmations),
        boundaries=boundaries or "",
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _custom_to_dict(row, include_content=True)


def update_skill(
    session: Session,
    ctx: Ctx,
    *,
    record_id: str | None = None,
    skill_key: str | None = None,
    skill_id: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    when_to_use: str | None = None,
    content: str | None = None,
    tools: list[Any] | None = None,
    confirmations: list[Any] | None = None,
    boundaries: str | None = None,
    new_skill_key: str | None = None,
) -> dict[str, Any]:
    if skill_id and not skill_id.startswith(f"{CUSTOM_MODULE_ID}."):
        raise AppError(
            "permission_denied",
            "Module-exported skills are read-only",
            details={"skill_id": skill_id},
        )
    row = _get_custom(
        session, ctx, record_id=record_id, skill_key=skill_key, skill_id=skill_id
    )
    if all(
        v is None
        for v in (
            title,
            summary,
            when_to_use,
            content,
            tools,
            confirmations,
            boundaries,
            new_skill_key,
        )
    ):
        raise AppError("validation_error", "provide at least one field to update")

    if new_skill_key is not None:
        norm = _normalize_key(new_skill_key)
        if norm != row.skill_key:
            clash = session.scalar(
                select(SkillItem).where(
                    SkillItem.tenant == ctx.tenant,
                    SkillItem.skill_key == norm,
                    SkillItem.id != row.id,
                )
            )
            if clash is not None:
                raise AppError("conflict", f"skill_key already exists: {norm}")
            row.skill_key = norm

    if title is not None:
        title = title.strip()
        if not title:
            raise AppError("validation_error", "title cannot be empty")
        row.title = title
    if summary is not None:
        row.summary = summary
    if when_to_use is not None:
        row.when_to_use = when_to_use
    if content is not None:
        row.content = content
    if tools is not None:
        row.tools_json = _dumps_list(tools)
    if confirmations is not None:
        row.confirmations_json = _dumps_list(confirmations)
    if boundaries is not None:
        row.boundaries = boundaries

    row.updated_by = ctx.user_id
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _custom_to_dict(row, include_content=True)


def delete_skill(
    session: Session,
    ctx: Ctx,
    *,
    record_id: str | None = None,
    skill_key: str | None = None,
    skill_id: str | None = None,
) -> dict[str, Any]:
    if skill_id and not skill_id.startswith(f"{CUSTOM_MODULE_ID}."):
        raise AppError(
            "permission_denied",
            "Module-exported skills are read-only",
            details={"skill_id": skill_id},
        )
    row = _get_custom(
        session, ctx, record_id=record_id, skill_key=skill_key, skill_id=skill_id
    )
    payload = _custom_to_dict(row, include_content=False)
    session.delete(row)
    session.flush()
    return {"deleted": True, "skill": payload}


def get_custom_skill_markdown(
    session: Session, *, tenant: int, skill_key: str
) -> str | None:
    """Load rendered markdown for MCP skill://custom/<key> (no team filter)."""
    row = session.scalar(
        select(SkillItem).where(
            SkillItem.tenant == tenant, SkillItem.skill_key == skill_key
        )
    )
    if row is None:
        return None
    return _render_skill_md(_custom_to_dict(row, include_content=True))


def list_custom_skills_for_catalog(
    session: Session, *, tenant: int
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SkillItem)
        .where(SkillItem.tenant == tenant)
        .order_by(SkillItem.skill_key.asc())
    )
    return [
        {
            "id": _custom_id(row.skill_key),
            "module": CUSTOM_MODULE_ID,
            "skill": row.skill_key,
            "uri": f"skill://{CUSTOM_MODULE_ID}/{row.skill_key}",
            "source": SOURCE_CUSTOM,
            "title": row.title,
            "readonly": False,
        }
        for row in rows
    ]
