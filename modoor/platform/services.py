"""External app registry — same Module contract as MODULE_CONTRACT.md.

Live services register a **manifest** (module.yaml shape) plus optional
**artifacts** (tool/skill/model bodies). Only names listed in
``exports.tools`` / ``exports.skills`` are L1; artifacts outside exports
are ignored.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _empty_manifest(module_id: str, app_name: str = "") -> dict[str, Any]:
    return {
        "id": module_id,
        "version": "0.0.0",
        "depends": [],
        "summary": "",
        "exports": {"tools": [], "skills": [], "menus": []},
        "ability": [],
        "risk_default": "medium",
        "ui-web": {
            "kind": "external",
            "label": app_name or module_id,
        },
    }


def _norm_manifest(raw: dict[str, Any] | None, *, module_id: str, app_name: str) -> dict[str, Any]:
    base = _empty_manifest(module_id, app_name)
    raw = dict(raw or {})
    mid = str(raw.get("id") or module_id).strip() or module_id
    exports_in = dict(raw.get("exports") or {})
    ui_in = dict(raw.get("ui-web") or {})
    ability = raw.get("ability")
    if ability is None:
        ability = raw.get("permissions") or []
    return {
        "id": mid,
        "version": str(raw.get("version") or "0.0.0"),
        "depends": list(raw.get("depends") or []),
        "summary": str(raw.get("summary") or ""),
        "exports": {
            "tools": [str(x) for x in (exports_in.get("tools") or [])],
            "skills": [str(x) for x in (exports_in.get("skills") or [])],
            "menus": list(exports_in.get("menus") or []),
        },
        "ability": [str(x) for x in (ability or [])],
        "risk_default": str(raw.get("risk_default") or "medium"),
        "ui-web": {
            "kind": "external",
            "label": ui_in.get("label") or app_name or mid,
            "home": ui_in.get("home") or ui_in.get("entry"),
            "entry": ui_in.get("entry") or ui_in.get("home"),
            "recommends": list(ui_in.get("recommends") or ["module_switcher", "logout"]),
        },
        "category": raw.get("category"),
        "events": list(raw.get("events") or []),
    }


def _norm_tool(item: dict[str, Any]) -> dict[str, Any] | None:
    name = item.get("name")
    if not name:
        return None
    return {
        "name": str(name),
        "description": str(item.get("description") or ""),
        "input_schema": item.get("input_schema") or {"type": "object", "properties": {}},
        "output_schema": item.get("output_schema"),
        "ability": item.get("ability") or item.get("permission"),
        "risk": item.get("risk") or "medium",
        "idempotency": bool(item.get("idempotency", False)),
        "side_effects": item.get("side_effects") or "read",
        "invoke_url": item.get("invoke_url"),
    }


def _norm_skill(item: dict[str, Any]) -> dict[str, Any] | None:
    sid = item.get("id") or item.get("name")
    if not sid:
        return None
    return {
        "id": str(sid),
        "title": str(item.get("title") or sid),
        "summary": str(item.get("summary") or ""),
        "when_to_use": str(item.get("when_to_use") or ""),
        "steps": list(item.get("steps") or []),
        "tools": [str(x) for x in (item.get("tools") or [])],
        "confirmations": list(item.get("confirmations") or []),
        "boundaries": item.get("boundaries") or item.get("禁忌") or item.get("禁忌 / 边界"),
        "content": item.get("content"),
        "content_url": item.get("content_url"),
    }


def _norm_model(item: dict[str, Any]) -> dict[str, Any] | None:
    name = item.get("name") or item.get("id")
    if not name:
        return None
    return {
        "name": str(name),
        "description": str(item.get("description") or ""),
        "fields": list(item.get("fields") or []),
    }


def _norm_artifacts(
    raw: dict[str, Any] | None, *, exports: dict[str, list]
) -> dict[str, list[dict[str, Any]]]:
    """Keep only artifacts whose names appear in manifest exports (L1 rule)."""
    raw = dict(raw or {})
    allowed_tools = set(exports.get("tools") or [])
    allowed_skills = set(exports.get("skills") or [])

    tools: list[dict[str, Any]] = []
    for item in raw.get("tools") or []:
        if not isinstance(item, dict):
            continue
        t = _norm_tool(item)
        if t and t["name"] in allowed_tools:
            tools.append(t)

    skills: list[dict[str, Any]] = []
    for item in raw.get("skills") or []:
        if not isinstance(item, dict):
            continue
        s = _norm_skill(item)
        if not s:
            continue
        if s["id"] not in allowed_skills:
            continue
        # Skill tools must ⊆ exports.tools
        s["tools"] = [n for n in s["tools"] if n in allowed_tools]
        skills.append(s)

    models: list[dict[str, Any]] = []
    for item in raw.get("models") or []:
        if not isinstance(item, dict):
            continue
        m = _norm_model(item)
        if m:
            models.append(m)

    return {"tools": tools, "skills": skills, "models": models}


@dataclass
class ServiceRecord:
    service_id: str
    module_id: str
    app_name: str
    entry_url: str
    health_url: str | None = None
    last_seen: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    # MODULE_CONTRACT: manifest ≈ module.yaml; artifacts ≈ tools/skills/models bodies
    manifest: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"tools": [], "skills": [], "models": []}
    )

    def touch(self) -> None:
        self.last_seen = datetime.now(timezone.utc).isoformat()

    @property
    def exports(self) -> dict[str, list]:
        return dict((self.manifest or {}).get("exports") or {})


_lock = threading.Lock()
_services: dict[str, ServiceRecord] = {}


def register_service(
    *,
    service_id: str,
    module_id: str,
    app_name: str,
    entry_url: str,
    health_url: str | None = None,
    meta: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> ServiceRecord:
    sid = service_id.strip()
    if not sid or not module_id.strip() or not entry_url.strip():
        raise ValueError("service_id, module_id, entry_url are required")

    mfest = _norm_manifest(manifest, module_id=module_id, app_name=app_name)
    arts = _norm_artifacts(artifacts, exports=mfest["exports"])
    rec = ServiceRecord(
        service_id=sid,
        module_id=mfest["id"],
        app_name=(app_name or (mfest.get("ui-web") or {}).get("label") or mfest["id"]).strip(),
        entry_url=entry_url.rstrip("/") + "/",
        health_url=health_url,
        meta=dict(meta or {}),
        manifest=mfest,
        artifacts=arts,
    )
    rec.touch()
    with _lock:
        _services[sid] = rec
    return rec


def set_manifest_artifacts(
    service_id: str,
    *,
    manifest: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> ServiceRecord | None:
    with _lock:
        rec = _services.get(service_id)
        if rec is None:
            return None
        if manifest is not None:
            rec.manifest = _norm_manifest(
                manifest, module_id=rec.module_id, app_name=rec.app_name
            )
        if artifacts is not None:
            rec.artifacts = _norm_artifacts(artifacts, exports=rec.exports)
        rec.touch()
        return rec



def heartbeat(
    service_id: str,
    *,
    entry_url: str | None = None,
    manifest: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> ServiceRecord | None:
    with _lock:
        rec = _services.get(service_id)
        if rec is None:
            return None
        if entry_url:
            rec.entry_url = entry_url.rstrip("/") + "/"
        if manifest is not None:
            rec.manifest = _norm_manifest(
                manifest, module_id=rec.module_id, app_name=rec.app_name
            )
        if artifacts is not None:
            rec.artifacts = _norm_artifacts(artifacts, exports=rec.exports)
        rec.touch()
        return rec


def unregister_service(service_id: str) -> bool:
    with _lock:
        return _services.pop(service_id, None) is not None


def list_services() -> list[dict[str, Any]]:
    with _lock:
        return [asdict(r) for r in sorted(_services.values(), key=lambda r: r.service_id)]


def get_by_module(module_id: str) -> ServiceRecord | None:
    with _lock:
        for rec in _services.values():
            if rec.module_id == module_id:
                return rec
    return None


def get_by_service_id(service_id: str) -> ServiceRecord | None:
    with _lock:
        return _services.get(service_id)


def get_entry_url(module_id: str) -> str | None:
    rec = get_by_module(module_id)
    return rec.entry_url if rec else None


def find_tool(tool_name: str) -> tuple[ServiceRecord, dict[str, Any]] | None:
    with _lock:
        for rec in _services.values():
            if tool_name not in (rec.exports.get("tools") or []):
                continue
            for tool in rec.artifacts.get("tools") or []:
                if tool.get("name") == tool_name:
                    return rec, tool
    return None


def find_skill(skill_id: str) -> tuple[ServiceRecord, dict[str, Any]] | None:
    with _lock:
        for rec in _services.values():
            allowed = set(rec.exports.get("skills") or [])
            for skill in rec.artifacts.get("skills") or []:
                sid = skill.get("id")
                if sid not in allowed:
                    continue
                if sid == skill_id or skill_id.endswith("." + str(sid).split(".")[-1]):
                    return rec, skill
    return None


def aggregated_exports() -> dict[str, Any]:
    """Hub view aligned with MODULE_CONTRACT exports + artifacts."""
    tools: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    with _lock:
        for rec in sorted(_services.values(), key=lambda r: r.service_id):
            base = {
                "service_id": rec.service_id,
                "module_id": rec.module_id,
                "app_name": rec.app_name,
                "entry_url": rec.entry_url,
                "source": "external",
            }
            manifests.append({**base, "manifest": rec.manifest})
            for tool in rec.artifacts.get("tools") or []:
                tools.append({**base, **tool})
            for skill in rec.artifacts.get("skills") or []:
                skills.append({**base, **skill})
            for model in rec.artifacts.get("models") or []:
                models.append({**base, **model})
    return {
        "manifests": manifests,
        "tools": tools,
        "skills": skills,
        "models": models,
        "services": list_services(),
    }


# Alias used by older call sites
def aggregated_capabilities() -> dict[str, Any]:
    return aggregated_exports()
