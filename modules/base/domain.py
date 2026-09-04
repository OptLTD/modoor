"""Base module: App / User / Role / Team (tenant-scoped RBAC)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError
from modoor.core.security import hash_password, verify_password

_CODE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class SystemTenant(Base):
    __tablename__ = "base_tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class SystemApp(Base):
    __tablename__ = "base_apps"
    __table_args__ = (
        UniqueConstraint("tenant", "code", name="uq_base_apps_tenant_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SystemTeam(Base):
    """Tenant-scoped team / org-unit tree (team ≡ org)."""

    __tablename__ = "base_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    parent: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    seqno: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SystemUser(Base):
    __tablename__ = "base_users"
    __table_args__ = (
        UniqueConstraint("tenant", "username", name="uq_base_users_tenant_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    realname: Mapped[str] = mapped_column(String(256))
    password: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SystemRole(Base):
    __tablename__ = "base_roles"
    __table_args__ = (
        UniqueConstraint(
            "tenant", "app_scope", "code", name="uq_base_roles_tenant_scope_code"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    app_id: Mapped[str | None] = mapped_column(
        ForeignKey("base_apps.id"), nullable=True, index=True
    )
    # "_tenant_" when app_id is null — makes uniqueness reliable on Postgres
    app_scope: Mapped[str] = mapped_column(String(36), default="_tenant_", index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: assigned user ids; ability/node codes
    users: Mapped[list] = mapped_column(JSON, default=list)
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def _norm_code(code: str, *, field: str = "code") -> str:
    value = (code or "").strip().lower()
    if not _CODE_RE.match(value):
        raise AppError(
            "validation_error",
            f"{field} must match ^[a-z][a-z0-9_-]{{1,63}}$",
        )
    return value


def _touch(obj: Any) -> None:
    obj.updated_at = datetime.now(timezone.utc)


def _app_dict(row: SystemApp) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant": row.tenant,
        "team_id": row.team_id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "active": row.active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _user_dict(row: SystemUser) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant": row.tenant,
        "team_id": row.team_id,
        "username": row.username,
        "realname": row.realname,
        "email": row.email,
        "active": row.active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _team_dict(row: SystemTeam) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "seqno": row.seqno,
        "tenant": row.tenant,
        "parent": row.parent,
        "active": row.active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _role_users(row: SystemRole) -> list[int]:
    raw = row.users if isinstance(row.users, list) else []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _role_nodes(row: SystemRole) -> list[str]:
    raw = row.nodes if isinstance(row.nodes, list) else []
    return sorted({str(x).strip() for x in raw if str(x).strip()})


def _role_dict(row: SystemRole) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant": row.tenant,
        "team_id": row.team_id,
        "app_id": row.app_id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "users": _role_users(row),
        "nodes": _role_nodes(row),
        "active": row.active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _scoped(stmt, ctx: Ctx, model):
    stmt = stmt.where(model.tenant == ctx.tenant)
    stmt = stmt.where(model.team_id == ctx.team_id)
    return stmt


def _tenant_dict(row: SystemTenant) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def get_tenant_by_name(session: Session, name: str) -> SystemTenant:
    name = (name or "").strip()
    if not name:
        raise AppError("validation_error", "tenant name is required")
    row = session.scalar(select(SystemTenant).where(SystemTenant.name == name))
    if row is None:
        raise AppError("not_found", f"Tenant not found: {name}")
    return row


def get_tenant(session: Session, tenant_id: int) -> SystemTenant:
    row = session.get(SystemTenant, tenant_id)
    if row is None:
        raise AppError("not_found", "Tenant not found")
    return row


def ensure_tenant(session: Session, name: str) -> dict[str, Any]:
    """Create tenant + same-named root team if missing. Idempotent."""
    name = (name or "").strip()
    if not name:
        raise AppError("validation_error", "tenant name is required")
    created_tenant = False
    created_team = False
    row = session.scalar(select(SystemTenant).where(SystemTenant.name == name))
    if row is None:
        row = SystemTenant(name=name)
        session.add(row)
        session.flush()
        created_tenant = True
    root = session.scalar(
        select(SystemTeam)
        .where(
            SystemTeam.tenant == row.id,
            SystemTeam.parent.is_(None),
            SystemTeam.name == name,
        )
        .order_by(SystemTeam.seqno, SystemTeam.id)
    )
    if root is None:
        root = session.scalar(
            select(SystemTeam)
            .where(SystemTeam.tenant == row.id, SystemTeam.parent.is_(None))
            .order_by(SystemTeam.seqno, SystemTeam.id)
        )
    if root is None:
        root = SystemTeam(
            tenant=row.id,
            parent=None,
            name=name,
            seqno=0,
            active=True,
            created_by=0,
        )
        session.add(root)
        session.flush()
        created_team = True
    return {
        "tenant": _tenant_dict(row),
        "team": _team_dict(root),
        "created_tenant": created_tenant,
        "created_team": created_team,
    }


def root_team_id(session: Session, tenant_id: int) -> int:
    root = session.scalar(
        select(SystemTeam)
        .where(SystemTeam.tenant == tenant_id, SystemTeam.parent.is_(None))
        .order_by(SystemTeam.seqno, SystemTeam.id)
    )
    if root is None:
        raise AppError("not_found", "Root team not found for tenant")
    return root.id


def _get_app(session: Session, ctx: Ctx, *, app_id: str | None = None, code: str | None = None) -> SystemApp:
    if app_id:
        row = session.get(SystemApp, app_id)
    elif code:
        row = session.scalar(
            select(SystemApp).where(
                SystemApp.tenant == ctx.tenant,
                SystemApp.code == _norm_code(code),
            )
        )
    else:
        raise AppError("validation_error", "app_id or code is required")
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "App not found")
    return row


def _get_user(
    session: Session, ctx: Ctx, *, user_id: int | None = None, username: str | None = None
) -> SystemUser:
    if user_id is not None:
        row = session.get(SystemUser, user_id)
    elif username:
        row = session.scalar(
            select(SystemUser).where(
                SystemUser.tenant == ctx.tenant,
                SystemUser.username == username.strip().lower(),
            )
        )
    else:
        raise AppError("validation_error", "user_id or username is required")
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "User not found")
    return row


def _get_role(
    session: Session, ctx: Ctx, *, role_id: str | None = None, code: str | None = None, app_id: str | None = None
) -> SystemRole:
    if role_id:
        row = session.get(SystemRole, role_id)
    elif code:
        stmt = select(SystemRole).where(
            SystemRole.tenant == ctx.tenant,
            SystemRole.code == _norm_code(code),
        )
        if app_id:
            stmt = stmt.where(SystemRole.app_id == app_id)
        else:
            stmt = stmt.where(SystemRole.app_id.is_(None))
        row = session.scalar(stmt)
    else:
        raise AppError("validation_error", "role_id or code is required")
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "Role not found")
    return row


# ---- App ----

def create_app(
    session: Session,
    ctx: Ctx,
    *,
    code: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    code = _norm_code(code)
    name = name.strip()
    if not name:
        raise AppError("validation_error", "name is required")
    exists = session.scalar(
        select(SystemApp).where(SystemApp.tenant == ctx.tenant, SystemApp.code == code)
    )
    if exists:
        raise AppError("conflict", f"app code already exists: {code}")
    row = SystemApp(
        id=str(uuid.uuid4()),
        tenant=ctx.tenant,
        team_id=ctx.team_id,
        code=code,
        name=name,
        description=description,
        active=True,
        created_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _app_dict(row)


def update_app(
    session: Session,
    ctx: Ctx,
    *,
    app_id: str | None = None,
    code: str | None = None,
    name: str | None = None,
    description: str | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    row = _get_app(session, ctx, app_id=app_id, code=code)
    if name is None and description is None and active is None:
        raise AppError("validation_error", "provide name, description, and/or active")
    if name is not None:
        name = name.strip()
        if not name:
            raise AppError("validation_error", "name cannot be empty")
        row.name = name
    if description is not None:
        row.description = description
    if active is not None:
        row.active = active
    _touch(row)
    session.flush()
    return _app_dict(row)


def get_app(
    session: Session, ctx: Ctx, *, app_id: str | None = None, code: str | None = None
) -> dict[str, Any]:
    return _app_dict(_get_app(session, ctx, app_id=app_id, code=code))


def list_apps(session: Session, ctx: Ctx, *, q: str | None = None, limit: int = 50) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise AppError("validation_error", "limit must be between 1 and 200")
    stmt = _scoped(select(SystemApp), ctx, SystemApp).order_by(SystemApp.code).limit(limit)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((SystemApp.code.ilike(like)) | (SystemApp.name.ilike(like)))
    rows = list(session.scalars(stmt))
    return {"items": [_app_dict(r) for r in rows], "count": len(rows)}


def delete_app(
    session: Session, ctx: Ctx, *, app_id: str | None = None, code: str | None = None
) -> dict[str, Any]:
    row = _get_app(session, ctx, app_id=app_id, code=code)
    roles = session.scalars(select(SystemRole).where(SystemRole.app_id == row.id)).all()
    if roles:
        raise AppError(
            "conflict",
            "cannot delete app while roles still reference it",
            details={"role_count": len(list(roles))},
        )
    payload = _app_dict(row)
    session.delete(row)
    session.flush()
    return {"deleted": True, "app": payload}


# ---- User ----

def create_user(
    session: Session,
    ctx: Ctx,
    *,
    username: str,
    realname: str,
    email: str | None = None,
    password: str | None = None,
    team_id: int | None = None,
) -> dict[str, Any]:
    username = username.strip().lower()
    if not username or " " in username:
        raise AppError("validation_error", "username is required and must not contain spaces")
    realname = realname.strip()
    if not realname:
        raise AppError("validation_error", "realname is required")
    exists = session.scalar(
        select(SystemUser).where(SystemUser.tenant == ctx.tenant, SystemUser.username == username)
    )
    if exists:
        raise AppError("conflict", f"username already exists: {username}")
    resolved_team = team_id if team_id is not None else ctx.team_id
    resolved_team = _get_team(session, ctx, team_id=resolved_team).id
    row = SystemUser(
        tenant=ctx.tenant,
        team_id=resolved_team,
        username=username,
        realname=realname,
        email=(email.strip() if email else None),
        password=hash_password(password) if password else None,
        active=True,
        created_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _user_dict(row)


def update_user(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int | None = None,
    username: str | None = None,
    realname: str | None = None,
    email: str | None = None,
    active: bool | None = None,
    password: str | None = None,
    team_id: int | None = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    row = _get_user(session, ctx, user_id=user_id, username=username)
    if (
        realname is None
        and email is None
        and active is None
        and password is None
        and team_id is ...
    ):
        raise AppError(
            "validation_error",
            "provide realname, email, active, password, and/or team_id",
        )
    if realname is not None:
        realname = realname.strip()
        if not realname:
            raise AppError("validation_error", "realname cannot be empty")
        row.realname = realname
    if email is not None:
        row.email = email.strip() or None
    if active is not None:
        row.active = active
    if password is not None:
        if not password:
            raise AppError("validation_error", "password cannot be empty")
        row.password = hash_password(password)
    if team_id is not ...:
        if team_id is None:
            raise AppError("validation_error", "team_id is required")
        row.team_id = _get_team(session, ctx, team_id=team_id).id
    _touch(row)
    session.flush()
    return _user_dict(row)


def get_user(
    session: Session, ctx: Ctx, *, user_id: int | None = None, username: str | None = None
) -> dict[str, Any]:
    return _user_dict(_get_user(session, ctx, user_id=user_id, username=username))


def list_users(
    session: Session,
    ctx: Ctx,
    *,
    q: str | None = None,
    team_id: int | None = None,
    include_descendants: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise AppError("validation_error", "limit must be between 1 and 200")
    stmt = (
        select(SystemUser)
        .where(SystemUser.tenant == ctx.tenant)
        .order_by(SystemUser.username)
        .limit(limit)
    )
    if team_id is not None:
        if include_descendants:
            ids = _team_descendant_ids(session, ctx, team_id)
            stmt = stmt.where(SystemUser.team_id.in_(ids))
        else:
            _get_team(session, ctx, team_id=team_id)
            stmt = stmt.where(SystemUser.team_id == team_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (SystemUser.username.ilike(like)) | (SystemUser.realname.ilike(like))
        )
    rows = list(session.scalars(stmt))
    return {"items": [_user_dict(r) for r in rows], "count": len(rows)}


def delete_user(
    session: Session, ctx: Ctx, *, user_id: int | None = None, username: str | None = None
) -> dict[str, Any]:
    row = _get_user(session, ctx, user_id=user_id, username=username)
    # Drop user id from all role.users JSON lists in tenant
    roles = list(session.scalars(select(SystemRole).where(SystemRole.tenant == ctx.tenant)))
    for role in roles:
        ids = _role_users(role)
        if row.id in ids:
            role.users = [i for i in ids if i != row.id]
            _touch(role)
    payload = _user_dict(row)
    session.delete(row)
    session.flush()
    return {"deleted": True, "user": payload}


# ---- Team (org unit) ----

def _get_team(session: Session, ctx: Ctx, *, team_id: int) -> SystemTeam:
    row = session.get(SystemTeam, team_id)
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "Team not found")
    return row


def _team_descendant_ids(session: Session, ctx: Ctx, root_id: int) -> list[int]:
    _get_team(session, ctx, team_id=root_id)
    rows = list(
        session.scalars(select(SystemTeam).where(SystemTeam.tenant == ctx.tenant))
    )
    children: dict[int | None, list[int]] = {}
    for r in rows:
        children.setdefault(r.parent, []).append(r.id)
    out: list[int] = []
    stack = [root_id]
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(children.get(cur, []))
    return out


def create_team(
    session: Session,
    ctx: Ctx,
    *,
    name: str,
    parent: int | None = None,
) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise AppError("validation_error", "name is required")
    if parent is not None:
        _get_team(session, ctx, team_id=parent)
        sibling_stmt = select(SystemTeam).where(
            SystemTeam.tenant == ctx.tenant,
            SystemTeam.parent == parent,
        )
    else:
        sibling_stmt = select(SystemTeam).where(
            SystemTeam.tenant == ctx.tenant,
            SystemTeam.parent.is_(None),
        )
    siblings = list(session.scalars(sibling_stmt))
    row = SystemTeam(
        tenant=ctx.tenant,
        parent=parent,
        name=name,
        seqno=len(siblings),
        active=True,
        created_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _team_dict(row)


def update_team(
    session: Session,
    ctx: Ctx,
    *,
    team_id: int,
    name: str | None = None,
    parent: int | None = ...,  # type: ignore[assignment]
    active: bool | None = None,
) -> dict[str, Any]:
    row = _get_team(session, ctx, team_id=team_id)
    if name is None and parent is ... and active is None:
        raise AppError("validation_error", "provide name, parent, and/or active")
    if name is not None:
        name = name.strip()
        if not name:
            raise AppError("validation_error", "name cannot be empty")
        row.name = name
    if parent is not ...:
        if parent == row.id:
            raise AppError("validation_error", "team cannot be its own parent")
        if parent is not None:
            if parent in _team_descendant_ids(session, ctx, row.id):
                raise AppError("validation_error", "cannot move team under its descendant")
            _get_team(session, ctx, team_id=parent)
            row.parent = parent
        else:
            row.parent = None
    if active is not None:
        row.active = active
    _touch(row)
    session.flush()
    return _team_dict(row)


def delete_team(session: Session, ctx: Ctx, *, team_id: int) -> dict[str, Any]:
    row = _get_team(session, ctx, team_id=team_id)
    if row.parent is None:
        raise AppError("conflict", "cannot delete the root team")
    child = session.scalar(
        select(SystemTeam).where(SystemTeam.tenant == ctx.tenant, SystemTeam.parent == row.id)
    )
    if child:
        raise AppError("conflict", "team has children; move or delete them first")
    fallback = row.parent
    users = session.scalars(
        select(SystemUser).where(SystemUser.tenant == ctx.tenant, SystemUser.team_id == row.id)
    ).all()
    for u in users:
        u.team_id = fallback
        _touch(u)
    payload = _team_dict(row)
    session.delete(row)
    session.flush()
    return {"deleted": True, "team": payload}


def list_team_tree(session: Session, ctx: Ctx) -> dict[str, Any]:
    rows = list(
        session.scalars(
            select(SystemTeam)
            .where(SystemTeam.tenant == ctx.tenant)
            .order_by(SystemTeam.seqno, SystemTeam.name)
        )
    )
    by_parent: dict[int | None, list[SystemTeam]] = {}
    for r in rows:
        by_parent.setdefault(r.parent, []).append(r)

    def build(pid: int | None) -> list[dict[str, Any]]:
        return [
            {**_team_dict(r), "children": build(r.id)}
            for r in by_parent.get(pid, [])
        ]

    tree = build(None)
    return {"tree": tree, "count": len(rows)}


# ---- Role ----

def create_role(
    session: Session,
    ctx: Ctx,
    *,
    code: str,
    name: str,
    app_id: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    code = _norm_code(code)
    name = name.strip()
    if not name:
        raise AppError("validation_error", "name is required")
    if app_id:
        _get_app(session, ctx, app_id=app_id)
    stmt = select(SystemRole).where(
        SystemRole.tenant == ctx.tenant,
        SystemRole.code == code,
    )
    stmt = stmt.where(SystemRole.app_id == app_id) if app_id else stmt.where(SystemRole.app_id.is_(None))
    if session.scalar(stmt):
        raise AppError("conflict", f"role code already exists: {code}")
    row = SystemRole(
        id=str(uuid.uuid4()),
        tenant=ctx.tenant,
        team_id=ctx.team_id,
        app_id=app_id,
        app_scope=app_id or "_tenant_",
        code=code,
        name=name,
        description=description,
        users=[],
        nodes=[],
        active=True,
        created_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _role_dict(row)


def update_role(
    session: Session,
    ctx: Ctx,
    *,
    role_id: str | None = None,
    code: str | None = None,
    app_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    row = _get_role(session, ctx, role_id=role_id, code=code, app_id=app_id)
    if name is None and description is None and active is None:
        raise AppError("validation_error", "provide name, description, and/or active")
    if name is not None:
        name = name.strip()
        if not name:
            raise AppError("validation_error", "name cannot be empty")
        row.name = name
    if description is not None:
        row.description = description
    if active is not None:
        row.active = active
    _touch(row)
    session.flush()
    return _role_dict(row)


def get_role(
    session: Session,
    ctx: Ctx,
    *,
    role_id: str | None = None,
    code: str | None = None,
    app_id: str | None = None,
) -> dict[str, Any]:
    return _role_dict(_get_role(session, ctx, role_id=role_id, code=code, app_id=app_id))


def list_roles(
    session: Session,
    ctx: Ctx,
    *,
    app_id: str | None = None,
    q: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise AppError("validation_error", "limit must be between 1 and 200")
    stmt = _scoped(select(SystemRole), ctx, SystemRole).order_by(SystemRole.code).limit(limit)
    if app_id:
        stmt = stmt.where(SystemRole.app_id == app_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((SystemRole.code.ilike(like)) | (SystemRole.name.ilike(like)))
    rows = list(session.scalars(stmt))
    return {"items": [_role_dict(r) for r in rows], "count": len(rows)}


def delete_role(
    session: Session,
    ctx: Ctx,
    *,
    role_id: str | None = None,
    code: str | None = None,
    app_id: str | None = None,
) -> dict[str, Any]:
    row = _get_role(session, ctx, role_id=role_id, code=code, app_id=app_id)
    payload = _role_dict(row)
    session.delete(row)
    session.flush()
    return {"deleted": True, "role": payload}


# ---- Assignment (JSON on role.users) ----

def assign_role(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int,
    role_id: str,
) -> dict[str, Any]:
    user = _get_user(session, ctx, user_id=user_id)
    role = _get_role(session, ctx, role_id=role_id)
    ids = _role_users(role)
    if user.id in ids:
        raise AppError("conflict", "role already assigned to user")
    role.users = [*ids, user.id]
    _touch(role)
    session.flush()
    return {
        "user_id": user.id,
        "role_id": role.id,
        "users": _role_users(role),
        "assigned_by": ctx.user_id,
    }


def revoke_role(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int,
    role_id: str,
) -> dict[str, Any]:
    user = _get_user(session, ctx, user_id=user_id)
    role = _get_role(session, ctx, role_id=role_id)
    ids = _role_users(role)
    if user.id not in ids:
        raise AppError("not_found", "role assignment not found")
    role.users = [i for i in ids if i != user.id]
    _touch(role)
    session.flush()
    return {"revoked": True, "user_id": user.id, "role_id": role.id}


def list_user_roles(session: Session, ctx: Ctx, *, user_id: int) -> dict[str, Any]:
    user = _get_user(session, ctx, user_id=user_id)
    roles_rows = list(
        session.scalars(select(SystemRole).where(SystemRole.tenant == ctx.tenant))
    )
    roles = [_role_dict(r) for r in roles_rows if user.id in _role_users(r)]
    return {"user_id": user.id, "roles": roles, "count": len(roles)}


def list_ability_catalog(settings: Any | None = None) -> dict[str, Any]:
    """Aggregate ability codes from all module manifests, grouped by module."""
    from modoor.platform.module_state import discover_manifests

    modules: list[dict[str, Any]] = []
    for m in discover_manifests(settings):
        abilities = [str(a) for a in (m.get("ability") or []) if str(a).strip()]
        if not abilities:
            continue
        modules.append(
            {
                "module_id": m["id"],
                "label": m.get("label") or m["id"],
                "i18n": m.get("i18n") or {},
                "abilities": abilities,
            }
        )
    flat = sorted({a for g in modules for a in g["abilities"]})
    return {"modules": modules, "abilities": flat, "count": len(flat)}


def list_role_nodes(session: Session, ctx: Ctx, *, role_id: str) -> dict[str, Any]:
    role = _get_role(session, ctx, role_id=role_id)
    nodes = _role_nodes(role)
    return {"role_id": role.id, "nodes": nodes, "count": len(nodes)}


def set_role_nodes(
    session: Session,
    ctx: Ctx,
    *,
    role_id: str,
    nodes: list[str],
) -> dict[str, Any]:
    role = _get_role(session, ctx, role_id=role_id)
    wanted = sorted({str(a).strip() for a in nodes if str(a).strip()})
    role.nodes = wanted
    _touch(role)
    session.flush()
    return list_role_nodes(session, ctx, role_id=role.id)


def authenticate_user(
    session: Session, *, tenant: int, username: str, password: str
) -> SystemUser:
    username = username.strip().lower()
    row = session.scalar(
        select(SystemUser).where(
            SystemUser.tenant == tenant,
            SystemUser.username == username,
        )
    )
    if row is None or not row.active:
        raise AppError("permission_denied", "Invalid username or password")
    if not row.password or not verify_password(password, row.password):
        raise AppError("permission_denied", "Invalid username or password")
    return row
