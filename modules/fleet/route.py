"""modules.fleet JSON API — /api/fleet."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modoor.core.db import session_scope
from modoor.web.api_util import ctx_of, http_error, require_user
from modules.fleet import domain as fleet_domain

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class VehicleCreate(BaseModel):
    plate_no: str = Field(min_length=1)
    model: str | None = None


@router.get("/vehicles")
def list_vehicles(request: Request) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return {"items": fleet_domain.list_vehicles(session, ctx_of(user))}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/vehicles")
def create_vehicle(request: Request, body: VehicleCreate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            item = fleet_domain.add_vehicle(
                session,
                ctx_of(user),
                plate_no=body.plate_no,
                model=body.model,
            )
        return {"ok": True, "item": item}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


def register(app, _kit) -> None:
    app.include_router(router)
