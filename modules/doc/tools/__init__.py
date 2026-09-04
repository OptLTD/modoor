"""Doc module MCP tools."""

from __future__ import annotations

from modoor.runtime.confirmation import (
    issue_confirmation_token,
    needs_confirmation_payload,
    verify_confirmation_token,
)
from modoor.runtime.tool import run_tool
from modules.doc import domain as doc_domain


def search_assets(q: str = "", tag: str = "", limit: int = 50) -> str:
    """Search doc assets by keyword and/or tag."""
    args = {"q": q, "tag": tag, "limit": limit}

    def _inner(session, ctx, _settings):
        return doc_domain.list_assets(
            session, ctx, q=q or None, tag=tag or None, limit=limit
        )

    return run_tool("doc.search_assets", args, _inner)


def list_assets(tag: str = "", limit: int = 50) -> str:
    """List recent doc assets (optional tag filter)."""
    args = {"tag": tag, "limit": limit}

    def _inner(session, ctx, _settings):
        return doc_domain.list_assets(session, ctx, tag=tag or None, limit=limit)

    return run_tool("doc.list_assets", args, _inner)


def get_asset(asset_id: str) -> str:
    """Get asset metadata (text truncated for size)."""
    args = {"asset_id": asset_id}

    def _inner(session, ctx, _settings):
        return {
            "asset": doc_domain.get_asset(
                session, ctx, asset_id=asset_id, text_limit=8_000
            )
        }

    return run_tool("doc.get_asset", args, _inner)


def get_asset_text(asset_id: str) -> str:
    """Get full extracted / stored text for an asset (for AI reading)."""
    args = {"asset_id": asset_id}

    def _inner(session, ctx, _settings):
        asset = doc_domain.get_asset(session, ctx, asset_id=asset_id, include_text=True)
        return {
            "id": asset["id"],
            "title": asset["title"],
            "filename": asset["filename"],
            "tags": asset["tags"],
            "text_status": asset.get("text_status") or "ready",
            "text_method": asset.get("text_method") or "",
            "text": asset.get("text") or "",
        }

    return run_tool("doc.get_asset_text", args, _inner)


def update_asset(
    asset_id: str,
    title: str | None = None,
    tags: list[str] | None = None,
    note: str | None = None,
) -> str:
    """Update asset title / tags / note."""
    args = {"asset_id": asset_id, "title": title, "tags": tags, "note": note}

    def _inner(session, ctx, _settings):
        return {
            "asset": doc_domain.update_asset(
                session,
                ctx,
                asset_id=asset_id,
                title=title,
                tags=tags,
                note=note,
            )
        }

    return run_tool("doc.update_asset", args, _inner)


def delete_asset(asset_id: str, confirmation_token: str | None = None) -> str:
    """Delete a doc asset (high risk). First call returns needs_confirmation."""
    args = {"asset_id": asset_id, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        asset = doc_domain.get_asset(session, ctx, asset_id=asset_id, include_text=False)
        confirm_args = {"asset_id": asset_id}
        if confirmation_token:
            verify_confirmation_token(
                secret=settings.modoor_confirm_secret,
                ctx=ctx,
                tool="doc.delete_asset",
                args=confirm_args,
                token=confirmation_token,
            )
            return doc_domain.delete_asset(session, ctx, asset_id=asset_id)

        token, expires_at = issue_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool="doc.delete_asset",
            args=confirm_args,
            ttl_seconds=settings.modoor_confirm_ttl_seconds,
        )
        return needs_confirmation_payload(
            token=token,
            expires_at=expires_at,
            tool="doc.delete_asset",
            summary={"id": asset["id"], "title": asset["title"]},
            args=confirm_args,
        )

    return run_tool("doc.delete_asset", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="doc.search_assets")(search_assets)
    mcp.tool(name="doc.list_assets")(list_assets)
    mcp.tool(name="doc.get_asset")(get_asset)
    mcp.tool(name="doc.get_asset_text")(get_asset_text)
    mcp.tool(name="doc.update_asset")(update_asset)
    mcp.tool(name="doc.delete_asset")(delete_asset)
