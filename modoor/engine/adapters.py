"""Model adapters: schema index ↔ domain ORM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from modoor.core.ctx import Ctx
from modoor.core.errors import AppError
from modoor.core.state import STATE_OFF, STATE_ON, sale_code, sale_label
from modoor.engine.query import QueryTerm, parse_query


class ModelAdapter(ABC):
    model: str

    @abstractmethod
    def search(
        self,
        session: Session,
        ctx: Ctx,
        *,
        query: dict[str, Any] | None,
        order: dict[str, Any] | None,
        page: int,
        size: int,
        field_keys: list[str],
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
        """Return values, count, totals."""

    @abstractmethod
    def get_values(self, session: Session, ctx: Ctx, uukey: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def upsert(
        self,
        session: Session,
        ctx: Ctx,
        batch: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def delete_keys(self, session: Session, ctx: Ctx, keys: list[str]) -> None:
        ...

    def refers(self, session: Session, ctx: Ctx) -> dict[str, Any]:
        """Optional lookup dicts for OPTIONAL/RELATION fields."""
        return {}


_ADAPTERS: dict[str, ModelAdapter] = {}


def register_adapter(adapter: ModelAdapter) -> None:
    _ADAPTERS[adapter.model] = adapter


def get_adapter(model: str) -> ModelAdapter:
    if model not in _ADAPTERS:
        # lazy import default adapters
        from modoor.engine import adapters as _adapters  # noqa: F401

    if model not in _ADAPTERS:
        raise AppError("not_found", f"no adapter for model: {model}")
    return _ADAPTERS[model]


def _parse_datetime(val: Any) -> datetime | None:
    if val in (None, ""):
        return None
    s = str(val).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise AppError("validation_error", f"invalid datetime: {val}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def flatten_pick(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    if "." in key:
        group, field = key.split(".", 1)
        nested = row.get(group)
        if isinstance(nested, dict) and field in nested:
            return nested[field]
        if field in row:
            return row[field]
    return None


def normalize_batch_row(row: dict[str, Any]) -> dict[str, Any]:
    """Prefer group.field keys; keep bare basic.* aliases collapsed."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in {"uukey", "model", "logid"}:
            out[k] = v
            continue
        if "." in k:
            out[k] = v
        else:
            # bare field — only fill if flat missing
            flat = f"basic.{k}"
            out.setdefault(flat, v)
    if "basic.uukey" not in out and row.get("uukey"):
        out["basic.uukey"] = row["uukey"]
    return out


def _truthy_on(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return int(val) == STATE_ON
    return str(val).strip().lower() in ("1", "true", "yes", "y", "active", "on")


def _as_on_off(val: Any) -> int | list[int]:
    if isinstance(val, list):
        return [STATE_ON if _truthy_on(v) else STATE_OFF for v in val]
    return STATE_ON if _truthy_on(val) else STATE_OFF


def _as_sale_state(val: Any) -> int | list[int]:
    if isinstance(val, list):
        return [sale_code(v) for v in val]
    return sale_code(val)


class SaleOrderAdapter(ModelAdapter):
    model = "sale.order"

    # schema index → ORM attribute
    COLS: dict[str, str] = {
        "basic.uukey": "id",
        "basic.utime": "created_at",
        "basic.status": "state",
        "basic.partner_name": "partner_name",
        "basic.note": "note",
    }

    def _to_values(self, order: Any, field_keys: list[str] | None = None) -> dict[str, Any]:
        total = sum((line.qty * line.unit_price) for line in (order.lines or []))
        raw = {
            "basic.uukey": order.id,
            "basic.utime": order.created_at.isoformat() if order.created_at else None,
            "basic.status": sale_label(order.state),
            "basic.partner_name": order.partner_name,
            "basic.note": order.note,
            "amount.total": float(total),
        }
        if field_keys is None:
            return raw
        return {k: raw.get(k) for k in field_keys if k in raw}

    def _apply_terms(self, stmt: Any, terms: list[QueryTerm]) -> Any:
        from modules.sale.domain import SaleOrder

        for term in terms:
            col_name = self.COLS.get(term.field)
            if not col_name:
                continue
            col = getattr(SaleOrder, col_name)
            op = term.op
            val = term.value
            if term.field == "basic.status":
                val = _as_sale_state(val)
            if op == "EQ":
                stmt = stmt.where(col == val)
            elif op == "NE":
                stmt = stmt.where(col != val)
            elif op == "IN":
                vals = val if isinstance(val, list) else [val]
                stmt = stmt.where(col.in_(vals))
            elif op == "LIKE":
                stmt = stmt.where(col.ilike(f"%{val}%") if hasattr(col, "ilike") else col.like(f"%{val}%"))
            elif op == "NIL":
                if val in (True, "true", 1, "1"):
                    stmt = stmt.where(col.is_(None))
                else:
                    stmt = stmt.where(col.is_not(None))
            elif op == "BTW" and isinstance(val, (list, tuple)) and len(val) >= 2:
                stmt = stmt.where(col >= val[0], col <= val[1])
            elif op == "GT":
                stmt = stmt.where(col > val)
            elif op == "GTE":
                stmt = stmt.where(col >= val)
            elif op == "LT":
                stmt = stmt.where(col < val)
            elif op == "LTE":
                stmt = stmt.where(col <= val)
        return stmt

    def search(
        self,
        session: Session,
        ctx: Ctx,
        *,
        query: dict[str, Any] | None,
        order: dict[str, Any] | None,
        page: int,
        size: int,
        field_keys: list[str],
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
        from modules.sale.domain import SaleOrder

        page = max(int(page or 1), 1)
        size = min(max(int(size or 50), 1), 500)
        terms = parse_query(query)
        base = select(SaleOrder).where(SaleOrder.tenant == ctx.tenant)
        base = self._apply_terms(base, terms)

        count = session.scalar(select(func.count()).select_from(base.subquery())) or 0

        order_field = (order or {}).get("field") or "basic.uukey"
        order_dir = str((order or {}).get("order") or "desc").lower()
        col_name = self.COLS.get(str(order_field), "id")
        col = getattr(SaleOrder, col_name, SaleOrder.id)
        ordered = base.order_by(desc(col) if order_dir == "desc" else asc(col))
        rows = session.scalars(
            ordered.options(selectinload(SaleOrder.lines)).offset((page - 1) * size).limit(size)
        ).all()
        values = [self._to_values(r, field_keys) for r in rows]

        totals: dict[str, Any] | None = None
        if "amount.total" in field_keys and values:
            totals = {
                "basic.uukey": len(values),
                "amount.total": round(sum(float(v.get("amount.total") or 0) for v in values), 2),
            }
        return values, int(count), totals

    def get_values(self, session: Session, ctx: Ctx, uukey: str) -> dict[str, Any] | None:
        from modules.sale.domain import SaleOrder

        order = session.get(SaleOrder, uukey)
        if order is None or order.tenant != ctx.tenant:
            return None
        return self._to_values(order)

    def upsert(
        self,
        session: Session,
        ctx: Ctx,
        batch: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        from modules.sale import domain as sale_domain
        from modules.sale.domain import SaleOrder

        records: list[dict[str, Any]] = []
        for raw in batch:
            row = normalize_batch_row(raw)
            uukey = str(row.get("basic.uukey") or row.get("uukey") or "").strip()
            partner = str(flatten_pick(row, "basic.partner_name") or "").strip()
            status = flatten_pick(row, "basic.status")
            note = flatten_pick(row, "basic.note")

            existing = session.get(SaleOrder, uukey) if uukey else None
            if existing and existing.tenant == ctx.tenant:
                if partner:
                    existing.partner_name = partner
                if status not in (None, ""):
                    existing.state = sale_code(status)
                if note is not None:
                    existing.note = str(note) if note != "" else None
                session.flush()
                current = self._to_values(existing)
                records.append(
                    {
                        "uukey": existing.id,
                        "model": self.model,
                        "opType": "UPDATE",
                        "exists": True,
                        "request": row,
                        "current": current,
                        "prepare": current,
                        "storage": {"basic": {
                            "uukey": existing.id,
                            "partner_name": existing.partner_name,
                            "status": sale_label(existing.state),
                            "note": existing.note,
                        }},
                        "changed": True,
                        "changes": {},
                        "objects": None,
                    }
                )
                continue

            # create — require partner; add placeholder line if none
            if not partner:
                raise AppError("validation_error", "basic.partner_name is required")
            created = sale_domain.create_order(
                session,
                ctx,
                partner_name=partner,
                lines=[{"product_name": "-", "qty": 1, "unit_price": 0}],
                note=str(note) if note not in (None, "") else None,
            )
            # if client sent preferred id and create used uuid — keep uuid as truth
            entity = session.get(SaleOrder, created["id"])
            assert entity is not None
            if status not in (None, "") and sale_code(status) != sale_code("draft"):
                entity.state = sale_code(status)
                session.flush()
            current = self._to_values(entity)
            records.append(
                {
                    "uukey": entity.id,
                    "model": self.model,
                    "opType": "INSERT",
                    "exists": False,
                    "request": row,
                    "current": current,
                    "prepare": current,
                    "storage": {"basic": {
                        "uukey": entity.id,
                        "partner_name": entity.partner_name,
                        "status": sale_label(entity.state),
                        "note": entity.note,
                    }},
                    "changed": True,
                    "changes": {},
                    "objects": None,
                }
            )
        return records

    def delete_keys(self, session: Session, ctx: Ctx, keys: list[str]) -> None:
        from modules.sale.domain import SaleOrder

        for key in keys:
            order = session.get(SaleOrder, key)
            if order is None or order.tenant != ctx.tenant:
                continue
            session.delete(order)
        session.flush()


class SystemUserAdapter(ModelAdapter):
    model = "base.user"

    COLS: dict[str, str] = {
        "basic.uukey": "uukey",
        "basic.utime": "utime",
        "basic.name": "name",
        "basic.phone": "phone",
        "basic.email": "email",
        "basic.remark": "remark",
        "basic.team_id": "team_id",
    }

    def _to_values(self, user: Any, field_keys: list[str] | None = None) -> dict[str, Any]:
        raw = {
            "basic.uukey": user.uukey,
            "basic.utime": user.utime.isoformat() if user.utime else None,
            "basic.state": str(int(user.state or 0)),
            "basic.username": user.username,
            "basic.realname": user.realname,
            "basic.name": user.name or "",
            "basic.phone": user.phone or "",
            "basic.email": user.email or "",
            "basic.remark": user.remark or "",
            "basic.active": "true" if user.active else "false",
            "basic.team_id": str(user.team_id) if user.team_id is not None else "",
        }
        if field_keys is None:
            return raw
        return {k: raw.get(k) for k in field_keys if k in raw}

    def _apply_terms(self, stmt: Any, terms: list[QueryTerm]) -> Any:
        from platform.base.domain import SystemLogin, SystemUser

        for term in terms:
            op = term.op
            val = term.value
            if term.field == "basic.username":
                col = SystemLogin.username
            elif term.field == "basic.realname":
                col = SystemLogin.realname
            elif term.field == "basic.active":
                col = SystemUser.state
                val = _as_on_off(val)
            elif term.field == "basic.state":
                col = SystemUser.state
                val = _as_on_off(val)
            else:
                col_name = self.COLS.get(term.field)
                if not col_name:
                    continue
                col = getattr(SystemUser, col_name)
            if term.field == "basic.team_id" and val is not None and not isinstance(val, list):
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    pass
            if term.field == "basic.team_id" and isinstance(val, list):
                casted = []
                for v in val:
                    try:
                        casted.append(int(v))
                    except (TypeError, ValueError):
                        casted.append(v)
                val = casted
            if op == "EQ":
                stmt = stmt.where(col == val)
            elif op == "NE":
                stmt = stmt.where(col != val)
            elif op == "IN":
                vals = val if isinstance(val, list) else [val]
                stmt = stmt.where(col.in_(vals))
            elif op == "LIKE":
                stmt = stmt.where(col.ilike(f"%{val}%") if hasattr(col, "ilike") else col.like(f"%{val}%"))
            elif op == "NIL":
                if val in (True, "true", 1, "1"):
                    stmt = stmt.where(col.is_(None))
                else:
                    stmt = stmt.where(col.is_not(None))
        return stmt

    def search(
        self,
        session: Session,
        ctx: Ctx,
        *,
        query: dict[str, Any] | None,
        order: dict[str, Any] | None,
        page: int,
        size: int,
        field_keys: list[str],
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
        from platform.base.domain import SystemLogin, SystemUser

        page = max(int(page or 1), 1)
        size = min(max(int(size or 50), 1), 500)
        terms = parse_query(query)
        base = (
            select(SystemUser)
            .options(selectinload(SystemUser.login))
            .join(SystemLogin, SystemUser.base_id == SystemLogin.id)
            .where(SystemUser.tenant == ctx.tenant)
        )
        base = self._apply_terms(base, terms)

        count = session.scalar(select(func.count()).select_from(base.subquery())) or 0

        order_field = (order or {}).get("field") or "basic.username"
        order_dir = str((order or {}).get("order") or "asc").lower()
        if order_field == "basic.username":
            col: Any = SystemLogin.username
        elif order_field == "basic.realname":
            col = SystemLogin.realname
        elif order_field == "basic.active":
            col = SystemUser.state
        else:
            col_name = self.COLS.get(str(order_field), "uukey")
            col = getattr(SystemUser, col_name, SystemUser.uukey)
        ordered = base.order_by(desc(col) if order_dir == "desc" else asc(col))
        rows = list(session.scalars(ordered.offset((page - 1) * size).limit(size)))
        values = [self._to_values(r, field_keys) for r in rows]
        return values, int(count), None

    def refers(self, session: Session, ctx: Ctx) -> dict[str, Any]:
        from platform.base import domain as base_domain

        return {"basic.team_id": base_domain.list_team_options(session, ctx)}

    def _get_entity(self, session: Session, ctx: Ctx, uukey: str):
        from platform.base.domain import SystemUser

        stmt = (
            select(SystemUser)
            .options(selectinload(SystemUser.login))
            .where(SystemUser.tenant == ctx.tenant)
        )
        row = session.scalar(stmt.where(SystemUser.uukey == uukey))
        if row is None and uukey.isdigit():
            row = session.scalar(stmt.where(SystemUser.id == int(uukey)))
        return row

    def get_values(self, session: Session, ctx: Ctx, uukey: str) -> dict[str, Any] | None:
        user = self._get_entity(session, ctx, uukey)
        if user is None:
            return None
        return self._to_values(user)

    def upsert(
        self,
        session: Session,
        ctx: Ctx,
        batch: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        from platform.base import domain as base_domain

        records: list[dict[str, Any]] = []
        for raw in batch:
            row = normalize_batch_row(raw)
            uukey = str(row.get("basic.uukey") or row.get("uukey") or "").strip()
            username = str(flatten_pick(row, "basic.username") or "").strip()
            realname = str(flatten_pick(row, "basic.realname") or "").strip()
            name = str(flatten_pick(row, "basic.name") or "").strip()
            phone = flatten_pick(row, "basic.phone")
            email = flatten_pick(row, "basic.email")
            remark = flatten_pick(row, "basic.remark")
            password = flatten_pick(row, "basic.password")
            team_raw = flatten_pick(row, "basic.team_id")
            utime = _parse_datetime(flatten_pick(row, "basic.utime"))

            team_id: int | None = None
            if team_raw not in (None, ""):
                team_id = int(team_raw)

            existing = self._get_entity(session, ctx, uukey) if uukey else None
            if existing:
                kwargs: dict[str, Any] = {"user_id": existing.id}
                if realname:
                    kwargs["realname"] = realname
                if name:
                    kwargs["name"] = name
                if phone is not None:
                    kwargs["phone"] = str(phone) if phone != "" else ""
                if remark is not None:
                    kwargs["remark"] = str(remark) if remark != "" else ""
                if email is not None:
                    kwargs["email"] = str(email) if email != "" else ""
                if team_id is not None:
                    kwargs["team_id"] = team_id
                if utime is not None:
                    kwargs["utime"] = utime
                if password not in (None, ""):
                    kwargs["password"] = str(password)
                updated = base_domain.update_user(session, ctx, **kwargs)
                entity = self._get_entity(session, ctx, updated["uukey"])
                assert entity is not None
                current = self._to_values(entity)
                records.append(
                    {
                        "uukey": entity.uukey,
                        "model": self.model,
                        "opType": "UPDATE",
                        "exists": True,
                        "request": row,
                        "current": current,
                        "prepare": current,
                        "storage": {"basic": current},
                        "changed": True,
                        "changes": {},
                        "objects": None,
                    }
                )
                continue

            if not name and not realname:
                raise AppError("validation_error", "name is required")
            display_name = name or realname
            created = base_domain.create_user(
                session,
                ctx,
                username=username or None,
                realname=realname or display_name,
                name=display_name,
                phone=str(phone).strip() if phone not in (None, "") else None,
                email=str(email).strip() if email not in (None, "") else None,
                remark=str(remark).strip() if remark not in (None, "") else None,
                password=str(password) if password not in (None, "") else None,
                team_id=team_id if team_id is not None else ctx.team_id,
                utime=utime,
            )
            entity = self._get_entity(session, ctx, created["uukey"])
            assert entity is not None
            current = self._to_values(entity)
            records.append(
                {
                    "uukey": entity.uukey,
                    "model": self.model,
                    "opType": "INSERT",
                    "exists": False,
                    "request": row,
                    "current": current,
                    "prepare": current,
                    "storage": {"basic": current},
                    "changed": True,
                    "changes": {},
                    "objects": None,
                }
            )
        return records

    def delete_keys(self, session: Session, ctx: Ctx, keys: list[str]) -> None:
        from platform.base import domain as base_domain

        for key in keys:
            entity = self._get_entity(session, ctx, str(key).strip())
            if entity is None:
                continue
            if entity.id == ctx.user_id:
                raise AppError("validation_error", "cannot delete the current user")
            try:
                base_domain.delete_user(session, ctx, user_id=entity.id)
            except AppError as exc:
                if exc.code == "not_found":
                    continue
                raise


def ensure_default_adapters() -> None:
    if "sale.order" not in _ADAPTERS:
        register_adapter(SaleOrderAdapter())
    if "base.user" not in _ADAPTERS:
        register_adapter(SystemUserAdapter())


# register on import
ensure_default_adapters()
