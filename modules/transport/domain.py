"""modules.transport / TMS domain — table prefix `tms_`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError

TABLE_PREFIX = "tms"


class TmsShipment(Base):
    __tablename__ = f"{TABLE_PREFIX}_shipment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    ref_no: Mapped[str] = mapped_column(String(64), index=True)
    origin: Mapped[str] = mapped_column(String(256))
    destination: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def _row(s: TmsShipment) -> dict[str, Any]:
    return {
        "id": s.id,
        "tenant": s.tenant,
        "ref_no": s.ref_no,
        "origin": s.origin,
        "destination": s.destination,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def list_shipments(session: Session, ctx: Ctx) -> list[dict[str, Any]]:
    stmt = (
        select(TmsShipment)
        .where(TmsShipment.tenant == ctx.tenant)
        .order_by(TmsShipment.created_at.desc())
    )
    return [_row(s) for s in session.scalars(stmt).all()]


def add_shipment(
    session: Session,
    ctx: Ctx,
    *,
    ref_no: str,
    origin: str,
    destination: str,
) -> dict[str, Any]:
    ref = (ref_no or "").strip().upper()
    if not ref:
        raise AppError("validation_error", "ref_no required")
    o = (origin or "").strip()
    d = (destination or "").strip()
    if not o or not d:
        raise AppError("validation_error", "origin and destination required")
    row = TmsShipment(
        id=str(uuid.uuid4()),
        tenant=ctx.tenant,
        ref_no=ref,
        origin=o,
        destination=d,
        status="draft",
    )
    session.add(row)
    session.flush()
    return _row(row)
