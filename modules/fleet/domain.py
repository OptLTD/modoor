"""modules.fleet / VMS domain — table prefix `vms_`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError

TABLE_PREFIX = "vms"


class VmsVehicle(Base):
    __tablename__ = f"{TABLE_PREFIX}_vehicle"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    plate_no: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def _row(v: VmsVehicle) -> dict[str, Any]:
    return {
        "id": v.id,
        "tenant": v.tenant,
        "plate_no": v.plate_no,
        "model": v.model,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def list_vehicles(session: Session, ctx: Ctx) -> list[dict[str, Any]]:
    stmt = (
        select(VmsVehicle)
        .where(VmsVehicle.tenant == ctx.tenant)
        .order_by(VmsVehicle.created_at.desc())
    )
    return [_row(v) for v in session.scalars(stmt).all()]


def add_vehicle(
    session: Session,
    ctx: Ctx,
    *,
    plate_no: str,
    model: str | None = None,
) -> dict[str, Any]:
    plate = (plate_no or "").strip().upper()
    if not plate:
        raise AppError("validation_error", "plate_no required")
    row = VmsVehicle(
        id=str(uuid.uuid4()),
        tenant=ctx.tenant,
        plate_no=plate,
        model=(model or "").strip() or None,
        status="idle",
    )
    session.add(row)
    session.flush()
    return _row(row)
