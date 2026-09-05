"""Skill module MCP tools."""

from __future__ import annotations

from typing import Any

from modoor.runtime.confirmation import (
    issue_confirmation_token,
    needs_confirmation_payload,
    verify_confirmation_token,
)
from modoor.runtime.tool import run_tool
from platform.skill import domain as skill_domain


def list_skills(
    source: str | None = None, q: str | None = None, limit: int = 100
) -> str:
    """List skills. source=module (read-only exports) | custom | omit for both."""
    args = {"source": source, "q": q, "limit": limit}

    def _inner(session, ctx, _settings):
        return skill_domain.list_skills(
            session, ctx, source=source, q=q, limit=limit
        )

    return run_tool("skill.list_skills", args, _inner)


def get_skill(
    skill_id: str | None = None,
    source: str | None = None,
    module: str | None = None,
    skill_key: str | None = None,
    record_id: str | None = None,
) -> str:
    """Get one skill (module skills are read-only; custom skills include editable fields)."""
    args = {
        "skill_id": skill_id,
        "source": source,
        "module": module,
        "skill_key": skill_key,
        "record_id": record_id,
    }

    def _inner(session, ctx, _settings):
        return skill_domain.get_skill(
            session,
            ctx,
            skill_id=skill_id,
            source=source,
            module=module,
            skill_key=skill_key,
            record_id=record_id,
        )

    return run_tool("skill.get_skill", args, _inner)


def create_skill(
    skill_key: str,
    title: str,
    summary: str = "",
    when_to_use: str = "",
    content: str = "",
    tools: list[Any] | None = None,
    confirmations: list[Any] | None = None,
    boundaries: str = "",
) -> str:
    """Create a tenant custom skill (module-exported skills cannot be created this way)."""
    args = {
        "skill_key": skill_key,
        "title": title,
        "summary": summary,
        "when_to_use": when_to_use,
        "content": content,
        "tools": tools,
        "confirmations": confirmations,
        "boundaries": boundaries,
    }

    def _inner(session, ctx, _settings):
        return skill_domain.create_skill(
            session,
            ctx,
            skill_key=skill_key,
            title=title,
            summary=summary,
            when_to_use=when_to_use,
            content=content,
            tools=tools,
            confirmations=confirmations,
            boundaries=boundaries,
        )

    return run_tool("skill.create_skill", args, _inner)


def update_skill(
    skill_id: str | None = None,
    record_id: str | None = None,
    skill_key: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    when_to_use: str | None = None,
    content: str | None = None,
    tools: list[Any] | None = None,
    confirmations: list[Any] | None = None,
    boundaries: str | None = None,
    new_skill_key: str | None = None,
) -> str:
    """Update a custom skill only. Module-exported skills return permission_denied."""
    args = {
        "skill_id": skill_id,
        "record_id": record_id,
        "skill_key": skill_key,
        "title": title,
        "summary": summary,
        "when_to_use": when_to_use,
        "content": content,
        "tools": tools,
        "confirmations": confirmations,
        "boundaries": boundaries,
        "new_skill_key": new_skill_key,
    }

    def _inner(session, ctx, _settings):
        return skill_domain.update_skill(
            session,
            ctx,
            skill_id=skill_id,
            record_id=record_id,
            skill_key=skill_key,
            title=title,
            summary=summary,
            when_to_use=when_to_use,
            content=content,
            tools=tools,
            confirmations=confirmations,
            boundaries=boundaries,
            new_skill_key=new_skill_key,
        )

    return run_tool("skill.update_skill", args, _inner)


def delete_skill(
    skill_id: str | None = None,
    record_id: str | None = None,
    skill_key: str | None = None,
    confirmation_token: str | None = None,
) -> str:
    """Delete a custom skill (high risk). Module skills cannot be deleted.

    First call without confirmation_token returns needs_confirmation.
    """
    args = {
        "skill_id": skill_id,
        "record_id": record_id,
        "skill_key": skill_key,
        "confirmation_token": confirmation_token,
    }

    def _inner(session, ctx, settings):
        skill = skill_domain.get_skill(
            session,
            ctx,
            skill_id=skill_id,
            record_id=record_id,
            skill_key=skill_key,
            source=skill_domain.SOURCE_CUSTOM,
        )
        if skill.get("readonly"):
            from modoor.core.errors import AppError

            raise AppError(
                "permission_denied",
                "Module-exported skills are read-only",
                details={"skill_id": skill.get("id")},
            )
        confirm_args = {
            "skill_id": skill_id,
            "record_id": record_id,
            "skill_key": skill_key,
        }
        if confirmation_token:
            verify_confirmation_token(
                secret=settings.modoor_confirm_secret,
                ctx=ctx,
                tool="skill.delete_skill",
                args=confirm_args,
                token=confirmation_token,
            )
            return skill_domain.delete_skill(
                session,
                ctx,
                skill_id=skill_id,
                record_id=record_id,
                skill_key=skill_key,
            )

        token, expires_at = issue_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool="skill.delete_skill",
            args=confirm_args,
            ttl_seconds=settings.modoor_confirm_ttl_seconds,
        )
        return needs_confirmation_payload(
            token=token,
            expires_at=expires_at,
            tool="skill.delete_skill",
            summary={
                "id": skill["id"],
                "skill_key": skill["skill_key"],
                "title": skill["title"],
            },
            args=confirm_args,
        )

    return run_tool("skill.delete_skill", args, _inner)


def register(mcp) -> None:
    mcp.tool(name="skill.list_skills")(list_skills)
    mcp.tool(name="skill.get_skill")(get_skill)
    mcp.tool(name="skill.create_skill")(create_skill)
    mcp.tool(name="skill.update_skill")(update_skill)
    mcp.tool(name="skill.delete_skill")(delete_skill)
