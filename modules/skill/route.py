"""modules.skill JSON API for Vue views."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modoor.core.db import session_scope
from modoor.web.api_util import ctx_of, http_error, require_user
from modules.skill import domain as skill_domain

router = APIRouter(prefix="/api/skill", tags=["skill"])


class SkillWrite(BaseModel):
    skill_key: str
    title: str
    summary: str = ""
    when_to_use: str = ""
    content: str = ""
    tools: list[Any] = Field(default_factory=list)
    confirmations: list[Any] = Field(default_factory=list)
    boundaries: str = ""
    record_id: str | None = None
    new_skill_key: str | None = None


@router.get("/skills")
def api_list_skills(
    request: Request, source: str | None = None, q: str | None = None
) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return skill_domain.list_skills(
                session, ctx_of(user), source=source, q=q, limit=200
            )
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.get("/skills/{skill_id:path}")
def api_get_skill(request: Request, skill_id: str) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            return {
                "skill": skill_domain.get_skill(
                    session, ctx_of(user), skill_id=skill_id
                )
            }
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.post("/skills")
def api_save_skill(request: Request, body: SkillWrite) -> dict[str, Any]:
    user = require_user(request)
    ctx = ctx_of(user)
    try:
        with session_scope() as session:
            if body.record_id:
                skill = skill_domain.update_skill(
                    session,
                    ctx,
                    record_id=body.record_id,
                    title=body.title,
                    summary=body.summary,
                    when_to_use=body.when_to_use,
                    content=body.content,
                    tools=body.tools,
                    confirmations=body.confirmations,
                    boundaries=body.boundaries,
                    new_skill_key=body.new_skill_key or body.skill_key,
                )
            else:
                skill = skill_domain.create_skill(
                    session,
                    ctx,
                    skill_key=body.skill_key,
                    title=body.title,
                    summary=body.summary,
                    when_to_use=body.when_to_use,
                    content=body.content,
                    tools=body.tools,
                    confirmations=body.confirmations,
                    boundaries=body.boundaries,
                )
        return {"ok": True, "skill": skill}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


@router.delete("/skills/{skill_id:path}")
def api_delete_skill(request: Request, skill_id: str) -> dict[str, Any]:
    user = require_user(request)
    try:
        with session_scope() as session:
            skill_domain.delete_skill(session, ctx_of(user), skill_id=skill_id)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        raise http_error(exc) from exc


def register(app, _kit) -> None:
    app.include_router(router)
