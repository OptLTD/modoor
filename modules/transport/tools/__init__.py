"""Transport module MCP tools."""

from __future__ import annotations

from modoor.runtime.tool import run_tool
from modules.transport import domain as transport_domain


def list_shipments() -> str:
    """List transport shipments for the current tenant (TMS)."""

    def _inner(session, ctx, _settings):
        return {"items": transport_domain.list_shipments(session, ctx)}

    return run_tool("transport.list_shipments", {}, _inner)


def add_shipment(ref_no: str, origin: str, destination: str) -> str:
    """Create a shipment in Transport / TMS.

    Args:
        ref_no: Shipment reference number.
        origin: Origin location.
        destination: Destination location.
    """
    args = {"ref_no": ref_no, "origin": origin, "destination": destination}

    def _inner(session, ctx, _settings):
        return transport_domain.add_shipment(
            session,
            ctx,
            ref_no=ref_no,
            origin=origin,
            destination=destination,
        )

    return run_tool("transport.add_shipment", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="transport.list_shipments")(list_shipments)
    mcp.tool(name="transport.add_shipment")(add_shipment)
