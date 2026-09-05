"""modules.transport JSON API — /api/transport."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modoor.core.db import session_scope
from modoor.web.api_util import ctx_of, http_error, require_user
from modules.transport import domain as transport_domain

router = APIRouter(prefix="/api/transport", tags=["transport"])


class ShipmentCreate(BaseModel):
    ref_no: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)


@router.get("/shipments")
def list_shipments(request: Request) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return {"items": transport_domain.list_shipments(session, ctx_of(user))}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/shipments")
def create_shipment(request: Request, body: ShipmentCreate) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            item = transport_domain.add_shipment(
                session,
                ctx_of(user),
                ref_no=body.ref_no,
                origin=body.origin,
                destination=body.destination,
            )
        return {"ok": True, "item": item}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


def register(app, _kit) -> None:
    app.include_router(router)
