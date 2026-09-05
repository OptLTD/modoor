"""Fleet module MCP tools."""

from __future__ import annotations

from modoor.runtime.tool import run_tool
from modules.fleet import domain as fleet_domain


def list_vehicles() -> str:
    """List fleet vehicles for the current tenant (VMS)."""

    def _inner(session, ctx, _settings):
        return {"items": fleet_domain.list_vehicles(session, ctx)}

    return run_tool("fleet.list_vehicles", {}, _inner)


def add_vehicle(plate_no: str, model: str | None = None) -> str:
    """Register a vehicle in Fleet / VMS.

    Args:
        plate_no: License plate number.
        model: Optional vehicle model.
    """
    args = {"plate_no": plate_no, "model": model}

    def _inner(session, ctx, _settings):
        return fleet_domain.add_vehicle(
            session, ctx, plate_no=plate_no, model=model
        )

    return run_tool("fleet.add_vehicle", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="fleet.list_vehicles")(list_vehicles)
    mcp.tool(name="fleet.add_vehicle")(add_vehicle)
