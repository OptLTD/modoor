from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from modoor.core.db import init_db
from modoor.core.settings import get_settings
from modoor.platform import services as service_registry
from modoor.platform.loader import register_module_tools
from modoor.runtime.tool import ok

mcp = MCPServer(
    "modoor",
    version="0.1.0",
    instructions=(
        "Modoor capability layer (AI-first registry hub). "
        "In-repo modules expose tools under platform/*/tools and modules/*/tools. "
        "External apps may optionally register a MODULE_CONTRACT manifest + artifacts "
        "via the service registry; invoke with external.call_tool. "
        "High-risk tools may return needs_confirmation."
    ),
)

_registered = False


def ensure_tools_registered() -> None:
    global _registered
    init_db()
    if _registered:
        return
    register_module_tools(mcp)
    _registered = True


def _local_skills() -> list[dict[str, Any]]:
    from modoor.platform.roots import module_pkg_roots

    skills: list[dict[str, Any]] = []
    for _pkg, root in module_pkg_roots():
        if not root.is_dir():
            continue
        for skill_path in sorted(root.glob("*/skills/*.md")):
            module_id = skill_path.parent.parent.name
            skill_name = skill_path.stem
            skills.append(
                {
                    "id": f"{module_id}.{skill_name}",
                    "module": module_id,
                    "skill": skill_name,
                    "uri": f"skill://{module_id}/{skill_name}",
                    "source": "module",
                    "readonly": True,
                    "path": str(skill_path),
                }
            )
    return skills


def _custom_skills() -> list[dict[str, Any]]:
    """Tenant custom skills from the skill module (editable)."""
    settings = get_settings()
    try:
        from platform.skill import domain as skill_domain
    except ImportError:
        return []
    from modoor.core.db import session_scope

    with session_scope() as session:
        from platform.base.domain import ensure_tenant

        tenant_id = int(
            ensure_tenant(
                session,
                settings.modoor_tenant,
                tenant_id=settings.modoor_tenant_id,
            )["tenant"]["id"]
        )
        return skill_domain.list_custom_skills_for_catalog(
            session, tenant=tenant_id
        )


def _external_skills() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for skill in service_registry.aggregated_capabilities().get("skills") or []:
        sid = skill.get("id") or skill.get("name")
        module_id = skill.get("module_id") or ""
        name = str(sid).split(".", 1)[-1] if sid else ""
        items.append(
            {
                "id": sid,
                "module": module_id,
                "skill": name,
                "uri": f"skill://{module_id}/{name}",
                "source": "external",
                "readonly": True,
                "title": skill.get("title") or sid,
                "service_id": skill.get("service_id"),
            }
        )
    return items


@mcp.resource("skill://{module_id}/{skill_name}")
def skill_resource(module_id: str, skill_name: str) -> str:
    """Load Skill from platform/|modules/, custom catalog, or a registered external app."""
    from modoor.platform.roots import module_dir

    path = module_dir(module_id) / "skills" / f"{skill_name}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")

    if module_id == "custom":
        try:
            from platform.skill import domain as skill_domain
        except ImportError as exc:
            raise FileNotFoundError(
                f"Skill not found: {module_id}/{skill_name}"
            ) from exc
        from modoor.core.db import session_scope

        with session_scope() as session:
            md = skill_domain.get_custom_skill_markdown(
                session,
                tenant=get_settings().modoor_tenant,
                skill_key=skill_name,
            )
        if md is not None:
            return md

    skill_id = f"{module_id}.{skill_name}"
    found = service_registry.find_skill(skill_id) or service_registry.find_skill(
        skill_name
    )
    if found:
        _rec, skill = found
        if skill.get("content"):
            return str(skill["content"])
        content_url = skill.get("content_url")
        if content_url:
            r = httpx.get(content_url, timeout=10.0)
            r.raise_for_status()
            return r.text
    raise FileNotFoundError(f"Skill not found: {module_id}/{skill_name}")


@mcp.tool(name="catalog.list_skills")
def catalog_list_skills() -> str:
    """List Skill documents: module (readonly), custom, and external apps."""
    ensure_tools_registered()
    skills = _local_skills() + _custom_skills() + _external_skills()
    return ok({"skills": skills})


@mcp.tool(name="catalog.list_capabilities")
def catalog_list_capabilities() -> str:
    """List AI capabilities known to Modoor (local module tools + external registry)."""
    ensure_tools_registered()
    external = service_registry.aggregated_capabilities()
    local_tools: list[dict[str, str]] = []
    # names from manifests
    from modoor.platform.module_state import discover_manifests

    for meta in discover_manifests():
        for name in meta.get("tools") or []:
            local_tools.append(
                {
                    "name": name,
                    "module_id": meta["id"],
                    "source": "module",
                }
            )
    return ok(
        {
            "module_tools": local_tools,
            "external_tools": external.get("tools") or [],
            "external_skills": external.get("skills") or [],
            "external_models": external.get("models") or [],
            "external_services": external.get("services") or [],
        }
    )


@mcp.tool(name="external.call_tool")
def external_call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> str:
    """Invoke a tool exported by a live external app (via its invoke_url)."""
    ensure_tools_registered()
    found = service_registry.find_tool(tool_name)
    if not found:
        return ok(
            {
                "status": "error",
                "error": {
                    "code": "not_found",
                    "message": f"external tool not registered: {tool_name}",
                },
            }
        )
    _rec, tool = found
    invoke_url = tool.get("invoke_url")
    if not invoke_url:
        return ok(
            {
                "status": "error",
                "error": {
                    "code": "misconfigured",
                    "message": f"tool {tool_name} has no invoke_url",
                },
            }
        )
    try:
        r = httpx.post(
            invoke_url,
            json={"arguments": arguments or {}, "tool": tool_name},
            headers={"X-API-Key": get_settings().modoor_api_key},
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return ok(
            {
                "status": "error",
                "error": {"code": "invoke_failed", "message": str(exc)},
            }
        )
    if isinstance(data, dict) and "status" in data:
        return ok(data)
    return ok({"status": "ok", "result": data})


def main() -> None:
    ensure_tools_registered()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
