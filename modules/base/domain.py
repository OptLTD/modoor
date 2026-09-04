"""Base module: App / User / Role / Team (tenant-scoped RBAC)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text, UniqueConstraint, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError
from modoor.core.security import hash_password, verify_password
from modoor.core.state import STATE_ON, as_on, is_on

_CODE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class SystemTenant(Base):
    __tablename__ = "base_tenant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class SystemApp(Base):
    __tablename__ = "base_app"
    __table_args__ = (
        UniqueConstraint("tenant", "code", name="uq_base_app_tenant_code"),
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


class SystemLogin(Base):
    """Global sign-in identity (not a business record; one login → many tenant users)."""

    __tablename__ = "base_login"
    __table_args__ = (
        UniqueConstraint("username", name="uq_base_login_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    password: Mapped[str | None] = mapped_column(String(256), nullable=True)
    realname: Mapped[str] = mapped_column(String(256), default="")
    current: Mapped[int | None] = mapped_column(
        ForeignKey("base_tenant.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    users: Mapped[list["SystemUser"]] = relationship(
        back_populates="login",
        primaryjoin="SystemUser.base_id==SystemLogin.id",
        foreign_keys="SystemUser.base_id",
    )


class SystemTeam(Base):
    """Tenant-scoped team / org-unit tree (team ≡ org)."""

    __tablename__ = "base_team"
    __table_args__ = (
        UniqueConstraint("tenant", "uukey", name="uq_base_team_tenant_uukey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uukey: Mapped[str] = mapped_column(String(32), index=True)
    utime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    name: Mapped[str] = mapped_column(String(256))
    seqno: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[int] = mapped_column(SmallInteger, default=STATE_ON)
    parent: Mapped[int] = mapped_column(Integer, index=True, default=0)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
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

    @property
    def active(self) -> bool:
        return is_on(self.state)


class SystemUser(Base):
    __tablename__ = "base_user"
    __table_args__ = (
        UniqueConstraint("tenant", "uukey", name="uq_base_user_tenant_uukey"),
        UniqueConstraint("tenant", "base_id", name="uq_base_user_tenant_base"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uukey: Mapped[str] = mapped_column(String(32), index=True)
    utime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    name: Mapped[str] = mapped_column(String(256), default="")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[int] = mapped_column(SmallInteger, default=STATE_ON)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    base_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
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

    login: Mapped[SystemLogin] = relationship(
        back_populates="users",
        primaryjoin="SystemUser.base_id==SystemLogin.id",
        foreign_keys="SystemUser.base_id",
    )

    @property
    def username(self) -> str:
        return self.login.username if self.login is not None else ""

    @property
    def realname(self) -> str:
        return self.login.realname if self.login is not None else ""

    @property
    def current(self) -> int | None:
        return self.login.current if self.login is not None else None

    @property
    def active(self) -> bool:
        return is_on(self.state)


class SystemRole(Base):
    __tablename__ = "base_role"
    __table_args__ = (
        UniqueConstraint(
            "tenant", "app_scope", "code", name="uq_base_role_tenant_scope_code"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    app_id: Mapped[str | None] = mapped_column(
        ForeignKey("base_app.id"), nullable=True, index=True
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _touch(obj: Any) -> None:
    obj.updated_at = _now()


def _is_head_parent(parent: int | None) -> bool:
    return parent is None or int(parent) == 0


def _head_parent_clause():
    return or_(SystemTeam.parent.is_(None), SystemTeam.parent == 0)


def _serialno(model: str, *, default_prefix: str, default_width: int = 5) -> tuple[str, int]:
    from modoor.engine.registry import get_bundle

    try:
        bundle = get_bundle(model)
    except KeyError:
        return default_prefix, default_width
    field = bundle.fields.get("basic.uukey") or {}
    extra = dict(field.get("extra") or {})
    model_extra = dict(bundle.model.get("extra") or {})
    prefix = str(extra.get("constant") or model_extra.get("constant") or default_prefix).strip()
    raw = extra.get("counting")
    if raw is None:
        raw = model_extra.get("counting", default_width)
    try:
        width = int(raw)
    except (TypeError, ValueError):
        width = default_width
    if width < 1:
        width = default_width
    return prefix or default_prefix, width


def _next_uukey(
    session: Session,
    model: type,
    *,
    prefix: str,
    width: int = 5,
    tenant: int | None = None,
) -> str:
    stmt = select(model.uukey).where(model.uukey.like(f"{prefix}%"))
    if tenant is not None and hasattr(model, "tenant"):
        stmt = stmt.where(model.tenant == tenant)
    max_n = 0
    for key in session.scalars(stmt).all():
        if not key:
            continue
        tail = str(key)[len(prefix) :]
        if tail.isdigit():
            max_n = max(max_n, int(tail))
    return f"{prefix}{max_n + 1:0{width}d}"


def _get_login_by_username(session: Session, username: str) -> SystemLogin | None:
    return session.scalar(
        select(SystemLogin).where(SystemLogin.username == username.strip().lower())
    )


def _norm_account(value: str | None) -> str:
    return (value or "").strip().lower()


def _apply_login_profile(
    row: SystemLogin,
    *,
    realname: str | None = None,
    tenant: int | None = None,
    overwrite_name: bool = False,
) -> None:
    if realname is not None:
        name = realname.strip()
        if name and (overwrite_name or not (row.realname or "").strip()):
            row.realname = name
    if tenant is not None and row.current is None:
        row.current = tenant


def _ensure_login(
    session: Session,
    ctx: Ctx,
    *,
    username: str,
    password: str | None = None,
    realname: str | None = None,
    overwrite_name: bool = False,
    overwrite_password: bool = False,
) -> SystemLogin:
    username = username.strip().lower()
    if not username or " " in username:
        raise AppError("validation_error", "username is required and must not contain spaces")
    row = _get_login_by_username(session, username)
    if row is None:
        row = SystemLogin(
            username=username,
            password=hash_password(password) if password else None,
            realname=(realname or "").strip(),
            current=ctx.tenant,
        )
        session.add(row)
        session.flush()
        return row
    _apply_login_profile(
        row, realname=realname, tenant=ctx.tenant, overwrite_name=overwrite_name
    )
    if password and (overwrite_password or not row.password):
        row.password = hash_password(password)
    _touch(row)
    session.flush()
    return row


def _bind_login_for_user(
    session: Session,
    ctx: Ctx,
    *,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    password: str | None = None,
    realname: str | None = None,
) -> SystemLogin:
    """Resolve login for an unbound employee: email/phone as username, reuse if present."""
    uname = _norm_account(username)
    mail = _norm_account(email)
    mobile = _norm_account(phone)
    if uname:
        return _ensure_login(
            session,
            ctx,
            username=uname,
            password=password,
            realname=realname,
            overwrite_name=True,
        )
    if not mail and not mobile:
        raise AppError("validation_error", "email or phone is required")
    for key in (mail, mobile):
        if not key:
            continue
        row = _get_login_by_username(session, key)
        if row is None:
            continue
        _apply_login_profile(
            row, realname=realname, tenant=ctx.tenant, overwrite_name=True
        )
        if password and not row.password:
            row.password = hash_password(password)
        _touch(row)
        session.flush()
        return row
    return _ensure_login(
        session,
        ctx,
        username=mail or mobile,
        password=password,
        realname=realname,
        overwrite_name=True,
    )


def _assert_unique_contacts(
    session: Session,
    tenant: int,
    *,
    email: str | None = None,
    phone: str | None = None,
    exclude_id: int | None = None,
) -> None:
    mail = (email or "").strip()
    mobile = (phone or "").strip()
    if mail:
        stmt = select(SystemUser.id).where(
            SystemUser.tenant == tenant,
            func.lower(func.btrim(SystemUser.email)) == mail.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(SystemUser.id != exclude_id)
        if session.scalar(stmt) is not None:
            raise AppError("conflict", f"email already exists: {mail}")
    if mobile:
        stmt = select(SystemUser.id).where(
            SystemUser.tenant == tenant,
            func.lower(func.btrim(SystemUser.phone)) == mobile.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(SystemUser.id != exclude_id)
        if session.scalar(stmt) is not None:
            raise AppError("conflict", f"phone already exists: {mobile}")


def _attach_login(session: Session, ctx: Ctx, row: SystemUser, login: SystemLogin) -> None:
    exists = session.scalar(
        select(SystemUser).where(
            SystemUser.tenant == ctx.tenant, SystemUser.base_id == login.id
        )
    )
    if exists is not None and exists.id != row.id:
        raise AppError("conflict", f"username already exists: {login.username}")
    row.base_id = login.id


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
        "uukey": row.uukey,
        "utime": row.utime.isoformat() if row.utime else None,
        "state": row.state,
        "tenant": row.tenant,
        "team_id": row.team_id,
        "base_id": row.base_id,
        "username": row.username,
        "realname": row.realname,
        "current": row.current,
        "name": row.name,
        "phone": row.phone,
        "email": row.email,
        "remark": row.remark,
        "active": row.active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _team_dict(row: SystemTeam) -> dict[str, Any]:
    return {
        "id": row.id,
        "uukey": row.uukey,
        "utime": row.utime.isoformat() if row.utime else None,
        "state": row.state,
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
            _head_parent_clause(),
            SystemTeam.name == name,
        )
        .order_by(SystemTeam.seqno, SystemTeam.id)
    )
    if root is None:
        root = session.scalar(
            select(SystemTeam)
            .where(SystemTeam.tenant == row.id, _head_parent_clause())
            .order_by(SystemTeam.seqno, SystemTeam.id)
        )
    if root is None:
        root = SystemTeam(
            tenant=row.id,
            uukey=_next_uukey(session, SystemTeam, prefix="TM", tenant=row.id),
            utime=_now(),
            state=STATE_ON,
            parent=0,
            name=name,
            seqno=0,
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
        .where(SystemTeam.tenant == tenant_id, _head_parent_clause())
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


def _user_query(session: Session):
    return select(SystemUser).options(selectinload(SystemUser.login))


def _get_user(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int | None = None,
    username: str | None = None,
    uukey: str | None = None,
) -> SystemUser:
    row: SystemUser | None = None
    stmt = _user_query(session).where(SystemUser.tenant == ctx.tenant)
    if user_id is not None:
        row = session.scalar(stmt.where(SystemUser.id == user_id))
    elif uukey:
        row = session.scalar(stmt.where(SystemUser.uukey == uukey.strip()))
    elif username:
        row = session.scalar(
            stmt.join(SystemLogin, SystemUser.base_id == SystemLogin.id).where(
                SystemLogin.username == username.strip().lower()
            )
        )
    else:
        raise AppError("validation_error", "user_id, uukey or username is required")
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "User not found")
    return row


def load_user(
    session: Session, user_id: int, *, tenant: int | None = None
) -> SystemUser | None:
    stmt = _user_query(session).where(SystemUser.id == user_id)
    if tenant is not None:
        stmt = stmt.where(SystemUser.tenant == tenant)
    return session.scalar(stmt)


def resolve_user_key(session: Session, ctx: Ctx, key: str | int) -> SystemUser:
    raw = str(key).strip()
    if raw.isdigit():
        return _get_user(session, ctx, user_id=int(raw))
    return _get_user(session, ctx, uukey=raw)


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
    username: str | None = None,
    realname: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    remark: str | None = None,
    password: str | None = None,
    team_id: int | None = None,
    name: str | None = None,
    utime: datetime | None = None,
) -> dict[str, Any]:
    local_name = (name or realname or "").strip()
    if not local_name:
        raise AppError("validation_error", "name is required")
    login_realname = (realname or local_name).strip()
    prefix, width = _serialno("base.user", default_prefix="USER")
    uukey = _next_uukey(
        session, SystemUser, prefix=prefix, width=width, tenant=ctx.tenant
    )
    mail = (email.strip() if email else None) or None
    mobile = (phone.strip() if phone else None) or None
    _assert_unique_contacts(session, ctx.tenant, email=mail, phone=mobile)
    login = _bind_login_for_user(
        session,
        ctx,
        username=username,
        email=mail,
        phone=mobile,
        password=password,
        realname=login_realname,
    )
    exists = session.scalar(
        select(SystemUser).where(
            SystemUser.tenant == ctx.tenant, SystemUser.base_id == login.id
        )
    )
    if exists:
        raise AppError("conflict", f"username already exists: {login.username}")
    resolved_team = team_id if team_id is not None else ctx.team_id
    resolved_team = _get_team(session, ctx, team_id=resolved_team).id
    row = SystemUser(
        tenant=ctx.tenant,
        uukey=uukey,
        utime=utime or _now(),
        state=STATE_ON,
        base_id=login.id,
        team_id=resolved_team,
        name=local_name,
        phone=(phone.strip() if phone else None),
        email=(email.strip() if email else None),
        remark=(remark.strip() if remark else None),
        created_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    session.refresh(row, attribute_names=["login"])
    return _user_dict(row)


def update_user(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int | None = None,
    username: str | None = None,
    uukey: str | None = None,
    realname: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    remark: str | None = None,
    email: str | None = None,
    active: bool | None = None,
    password: str | None = None,
    team_id: int | None = ...,  # type: ignore[assignment]
    utime: datetime | None = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    row = _get_user(session, ctx, user_id=user_id, username=username, uukey=uukey)
    if (
        realname is None
        and name is None
        and phone is None
        and remark is None
        and email is None
        and active is None
        and password is None
        and team_id is ...
        and utime is ...
    ):
        raise AppError(
            "validation_error",
            "provide realname, name, phone, remark, email, active, password, team_id, and/or utime",
        )
    if name is not None:
        row.name = name.strip()
    next_phone = phone.strip() or None if phone is not None else row.phone
    next_email = email.strip() or None if email is not None else row.email
    if email is not None or phone is not None:
        _assert_unique_contacts(
            session,
            ctx.tenant,
            email=next_email if email is not None else None,
            phone=next_phone if phone is not None else None,
            exclude_id=row.id,
        )
    if phone is not None:
        row.phone = next_phone
    if remark is not None:
        row.remark = remark.strip() or None
    if email is not None:
        row.email = next_email
    if active is not None:
        if active is False and row.id == ctx.user_id:
            raise AppError("validation_error", "cannot disable the current user")
        row.state = as_on(active)
    login_realname = None
    if realname is not None:
        realname = realname.strip()
        if not realname:
            raise AppError("validation_error", "realname cannot be empty")
        login_realname = realname
    elif name is not None:
        login_realname = row.name or None
    if row.login is None:
        login = _bind_login_for_user(
            session,
            ctx,
            email=row.email,
            phone=row.phone,
            password=password,
            realname=login_realname or row.name,
        )
        _attach_login(session, ctx, row, login)
        session.flush()
        session.refresh(row, attribute_names=["login"])
    else:
        if login_realname:
            _apply_login_profile(row.login, realname=login_realname, overwrite_name=True)
            _touch(row.login)
        if password is not None:
            if not password:
                raise AppError("validation_error", "password cannot be empty")
            row.login.password = hash_password(password)
            _touch(row.login)
    if team_id is not ...:
        if team_id is None:
            raise AppError("validation_error", "team_id is required")
        row.team_id = _get_team(session, ctx, team_id=team_id).id
    if utime is not ...:
        if utime is None:
            raise AppError("validation_error", "utime is required")
        row.utime = utime
    _touch(row)
    session.flush()
    return _user_dict(row)


def get_user(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int | None = None,
    username: str | None = None,
    uukey: str | None = None,
) -> dict[str, Any]:
    return _user_dict(_get_user(session, ctx, user_id=user_id, username=username, uukey=uukey))


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
        _user_query(session)
        .where(SystemUser.tenant == ctx.tenant)
        .join(SystemLogin, SystemUser.base_id == SystemLogin.id)
        .order_by(SystemLogin.username)
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
            (SystemLogin.username.ilike(like))
            | (SystemLogin.realname.ilike(like))
            | (SystemUser.name.ilike(like))
        )
    rows = list(session.scalars(stmt))
    return {"items": [_user_dict(r) for r in rows], "count": len(rows)}


def delete_user(
    session: Session,
    ctx: Ctx,
    *,
    user_id: int | None = None,
    username: str | None = None,
    uukey: str | None = None,
) -> dict[str, Any]:
    row = _get_user(session, ctx, user_id=user_id, username=username, uukey=uukey)
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
    # Flat org: every team hangs directly under the head team.
    parent = root_team_id(session, ctx.tenant)
    siblings = list(
        session.scalars(
            select(SystemTeam).where(
                SystemTeam.tenant == ctx.tenant,
                SystemTeam.parent == parent,
            )
        )
    )
    row = SystemTeam(
        tenant=ctx.tenant,
        uukey=_next_uukey(session, SystemTeam, prefix="TM", tenant=ctx.tenant),
        utime=_now(),
        state=STATE_ON,
        parent=parent,
        name=name,
        seqno=len(siblings),
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
        if _is_head_parent(row.parent):
            raise AppError("validation_error", "cannot reparent the head team")
        head = root_team_id(session, ctx.tenant)
        if parent is None or parent != head:
            raise AppError("validation_error", "teams must hang under the head team")
        if parent == row.id:
            raise AppError("validation_error", "team cannot be its own parent")
        row.parent = parent
    if active is not None:
        row.state = as_on(active)
    _touch(row)
    session.flush()
    return _team_dict(row)


def delete_team(session: Session, ctx: Ctx, *, team_id: int) -> dict[str, Any]:
    row = _get_team(session, ctx, team_id=team_id)
    if _is_head_parent(row.parent):
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


def list_team_options(session: Session, ctx: Ctx) -> list[dict[str, str]]:
    rows = list(
        session.scalars(
            select(SystemTeam)
            .where(SystemTeam.tenant == ctx.tenant)
            .order_by(SystemTeam.seqno, SystemTeam.id)
        )
    )
    rows.sort(key=lambda r: (r.parent is not None, r.seqno, r.id))
    return [{"uukey": str(r.id), "label": r.name} for r in rows]


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
    login = _get_login_by_username(session, username)
    if login is None:
        raise AppError("permission_denied", "Invalid username or password")
    if not login.password or not verify_password(password, login.password):
        raise AppError("permission_denied", "Invalid username or password")
    row = session.scalar(
        _user_query(session).where(
            SystemUser.tenant == tenant,
            SystemUser.base_id == login.id,
        )
    )
    if row is None or not row.active:
        raise AppError("permission_denied", "Invalid username or password")
    login.current = tenant
    _touch(login)
    return row
