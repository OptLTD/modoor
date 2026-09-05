"""Wiki module MCP tools."""

from __future__ import annotations

from modoor.runtime.confirmation import (
    issue_confirmation_token,
    needs_confirmation_payload,
    verify_confirmation_token,
)
from modoor.runtime.tool import run_tool
from platform.wiki import domain as wiki_domain


def create_project(name: str, description: str = "", home_title: str = "Home") -> str:
    """Create a wiki project with a home page."""
    args = {"name": name, "description": description, "home_title": home_title}

    def _inner(session, ctx, _settings):
        return wiki_domain.create_project(
            session, ctx, name=name, description=description, home_title=home_title
        )

    return run_tool("wiki.create_project", args, _inner)


def list_projects() -> str:
    """List wiki projects for the tenant."""

    def _inner(session, ctx, _settings):
        return wiki_domain.list_projects(session, ctx)

    return run_tool("wiki.list_projects", {}, _inner)


def create_page(
    project_id: str,
    title: str,
    body: str | None = None,
    parent_id: str | None = None,
) -> str:
    """Create a wiki page under a project (optional parent for hierarchy). Body is BlockNote JSON."""
    args = {
        "project_id": project_id,
        "title": title,
        "body": body,
        "parent_id": parent_id,
    }

    def _inner(session, ctx, _settings):
        return wiki_domain.create_page(
            session,
            ctx,
            project_id=project_id,
            title=title,
            body=body,
            parent_id=parent_id,
        )

    return run_tool("wiki.create_page", args, _inner)


def update_page(
    page_id: str,
    title: str | None = None,
    body: str | None = None,
) -> str:
    """Update title/body of an existing wiki page by id."""
    args = {"page_id": page_id, "title": title, "body": body}

    def _inner(session, ctx, _settings):
        return wiki_domain.update_page(
            session, ctx, page_id=page_id, title=title, body=body
        )

    return run_tool("wiki.update_page", args, _inner)


def get_page(page_id: str) -> str:
    """Get a wiki page by id."""
    args = {"page_id": page_id}

    def _inner(session, ctx, _settings):
        return wiki_domain.get_page(session, ctx, page_id=page_id)

    return run_tool("wiki.get_page", args, _inner)


def list_pages(project_id: str | None = None, q: str | None = None, limit: int = 50) -> str:
    """List wiki pages (metadata). Optional project_id and title filter q."""
    args = {"project_id": project_id, "q": q, "limit": limit}

    def _inner(session, ctx, _settings):
        return wiki_domain.list_pages(
            session, ctx, project_id=project_id, q=q, limit=limit
        )

    return run_tool("wiki.list_pages", args, _inner)


def delete_page(page_id: str, confirmation_token: str | None = None) -> str:
    """Delete a wiki page (high risk). Cannot delete project home page.

    First call without confirmation_token returns needs_confirmation.
    """
    args = {"page_id": page_id, "confirmation_token": confirmation_token}

    def _inner(session, ctx, settings):
        page = wiki_domain.get_page(session, ctx, page_id=page_id)
        confirm_args = {"page_id": page_id}
        if confirmation_token:
            verify_confirmation_token(
                secret=settings.modoor_confirm_secret,
                ctx=ctx,
                tool="wiki.delete_page",
                args=confirm_args,
                token=confirmation_token,
            )
            return wiki_domain.delete_page(session, ctx, page_id=page_id)

        token, expires_at = issue_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool="wiki.delete_page",
            args=confirm_args,
            ttl_seconds=settings.modoor_confirm_ttl_seconds,
        )
        return needs_confirmation_payload(
            token=token,
            expires_at=expires_at,
            tool="wiki.delete_page",
            summary={"id": page["id"], "title": page["title"]},
            args=confirm_args,
        )

    return run_tool("wiki.delete_page", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="wiki.create_project")(create_project)
    mcp.tool(name="wiki.list_projects")(list_projects)
    mcp.tool(name="wiki.create_page")(create_page)
    mcp.tool(name="wiki.update_page")(update_page)
    mcp.tool(name="wiki.get_page")(get_page)
    mcp.tool(name="wiki.list_pages")(list_pages)
    mcp.tool(name="wiki.delete_page")(delete_page)
