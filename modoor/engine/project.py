"""Project config/tables/inputs into TableSchema / InputSchema (worth FE shape)."""

from __future__ import annotations

import copy
import re
from typing import Any

from modoor.engine.registry import ModelBundle


def _field_key(raw: dict[str, Any], fallback: str) -> str:
    return str(raw.get("uukey") or raw.get("index") or fallback)


def normalize_field(key: str, raw: dict[str, Any], *, group_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    data = copy.deepcopy(raw)
    group = str(data.get("group") or (key.split(".", 1)[0] if "." in key else "basic"))
    field = str(data.get("field") or (key.split(".", 1)[-1] if "." in key else key))
    gmeta = group_meta or {}
    extra = dict(data.get("extra") or {})
    refer = data.get("refer")
    if not refer and str(data.get("ftype") or "").upper() == "RELATION":
        using = str(data.get("using") or extra.get("relation") or "")
        if using:
            refer = {
                "uukey": "",
                "keyby": str(extra.get("dataKey") or "basic.uukey"),
                "txtby": str(extra.get("textKey") or "basic.name"),
                "image": "",
                "using": using,
            }
            extra.setdefault("relation", using)
    out: dict[str, Any] = {
        "uukey": _field_key(data, key),
        "gtype": data.get("gtype") or gmeta.get("gtype") or "FLATTEN",
        "gname": data.get("gname") or gmeta.get("title") or group,
        "ftype": str(data.get("ftype") or "STRINGS"),
        "group": group,
        "field": field,
        "label": data.get("label") or field,
        "index": data.get("index") or key,
        "shown": True if data.get("shown") is None else bool(data.get("shown")),
        "extra": extra,
    }
    if data.get("seqno") is not None:
        out["seqno"] = data["seqno"]
    if data.get("width") is not None:
        out["width"] = data["width"]
    if data.get("using"):
        out["using"] = data["using"]
    if refer:
        out["refer"] = refer
    if extra.get("options"):
        out["options"] = extra["options"]
    return out


def _match_field_keys(pattern: str, all_keys: list[str]) -> list[str]:
    if pattern == ".*":
        return list(all_keys)
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return [k for k in all_keys if k.startswith(prefix)]
    if "*" in pattern or "?" in pattern:
        rx = re.compile("^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$")
        return [k for k in all_keys if rx.match(k)]
    return [pattern] if pattern in all_keys else []


def resolve_view_fields(
    bundle: ModelBundle,
    *,
    using: str,
    kind: str,
) -> tuple[dict[str, Any], list[str]]:
    """Return (view_def, ordered field keys). kind = table|input."""
    catalog = bundle.tables if kind == "table" else bundle.inputs
    view = catalog.get(using) or catalog.get("default") or {}
    view = dict(view)
    all_keys = sorted(
        bundle.fields.keys(),
        key=lambda k: int(bundle.fields[k].get("seqno") or 9999),
    )
    patterns = list(view.get("fields") or ([".*"] if kind == "table" else all_keys))
    if not patterns and kind == "input":
        groups = list(view.get("groups") or [])
        if groups:
            patterns = [k for k in all_keys if (bundle.fields[k].get("group") in groups)]
        else:
            patterns = [".*"]
    ordered: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        for key in _match_field_keys(str(pat), all_keys):
            if key not in seen:
                ordered.append(key)
                seen.add(key)
    hidden = set(view.get("hidden") or [])
    ordered = [k for k in ordered if k not in hidden]
    return view, ordered


def build_source(bundle: ModelBundle) -> dict[str, Any]:
    groups = {}
    for gk, g in bundle.groups.items():
        groups[gk] = copy.deepcopy(g)
        groups[gk].setdefault("uukey", gk)
        groups[gk].setdefault("model", bundle.uukey)
    fields = {
        key: normalize_field(key, raw, group_meta=groups.get(str(raw.get("group") or "")))
        for key, raw in bundle.fields.items()
    }
    return {
        "model": copy.deepcopy(bundle.model),
        "scene": "",
        "fields": fields,
        "groups": groups,
        "tables": copy.deepcopy(bundle.tables),
        "inputs": copy.deepcopy(bundle.inputs),
        "clicks": copy.deepcopy(bundle.clicks),
    }


def option_refers(fields: list[dict[str, Any]]) -> dict[str, Any]:
    refers: dict[str, Any] = {}
    for f in fields:
        extra = f.get("extra") or {}
        opts = f.get("options") or extra.get("options") or []
        if opts:
            refers[f["uukey"]] = [
                {"uukey": o.get("uukey") or o.get("value"), "label": o.get("label")}
                for o in opts
                if isinstance(o, dict)
            ]
        dict_key = extra.get("dictKey")
        if dict_key and opts:
            # also expose short dict key suffix for worth parity
            short = str(dict_key).split(":", 1)[-1]
            refers.setdefault(short, refers[f["uukey"]])
    return refers


def project_table(
    bundle: ModelBundle,
    *,
    using: str,
    scene: str,
    page: int = 1,
    size: int = 50,
    query: dict[str, Any] | None = None,
    order: dict[str, Any] | None = None,
) -> dict[str, Any]:
    view, keys = resolve_view_fields(bundle, using=using, kind="table")
    groups_meta = bundle.groups
    fields = [
        normalize_field(k, bundle.fields[k], group_meta=groups_meta.get(str(bundle.fields[k].get("group") or "")))
        for k in keys
        if k in bundle.fields
    ]
    for f in fields:
        f["shown"] = True
    click_ids = list(view.get("clicks") or [])
    clicks = []
    for cid in click_ids:
        raw = bundle.clicks.get(cid)
        if not raw:
            continue
        item = copy.deepcopy(raw)
        item.setdefault("uukey", cid)
        clicks.append(item)
    sticky = list(view.get("sticky") or [])
    if not sticky and any(f["uukey"] == "basic.uukey" for f in fields):
        sticky = ["basic.uukey"]
    default_query = dict(view.get("query") or {})
    if query:
        default_query.update(query)
    default_order = order or {"field": "basic.uukey", "order": "desc"}
    groups = [
        {
            **copy.deepcopy(g),
            "uukey": gk,
            "model": g.get("model") or bundle.uukey,
        }
        for gk, g in sorted(
            groups_meta.items(),
            key=lambda kv: int((kv[1] or {}).get("seqno") or 0),
        )
    ]
    return {
        "model": bundle.uukey,
        "using": using,
        "title": view.get("title") or bundle.model.get("title") or bundle.uukey,
        "sticky": sticky,
        "groups": groups,
        "fields": fields,
        "clicks": clicks,
        "refers": option_refers(fields),
        "others": dict(view.get("extra") or {}),
        "request": {
            "model": bundle.uukey,
            "uukey": "",
            "scene": scene or "SEARCH",
            "logid": "",
            "page": page,
            "size": size,
            "using": using,
            "query": default_query,
            "order": default_order,
        },
    }


def project_input(
    bundle: ModelBundle,
    *,
    using: str,
    scene: str,
    uukey: str = "",
) -> dict[str, Any]:
    view, keys = resolve_view_fields(bundle, using=using, kind="input")
    groups_meta = bundle.groups
    group_ids = list(view.get("groups") or list(groups_meta.keys()))
    fields = [
        normalize_field(k, bundle.fields[k], group_meta=groups_meta.get(str(bundle.fields[k].get("group") or "")))
        for k in keys
        if k in bundle.fields
    ]
    groups = []
    for gk in group_ids:
        g = groups_meta.get(gk)
        if not g:
            continue
        item = copy.deepcopy(g)
        item.setdefault("uukey", gk)
        item.setdefault("model", bundle.uukey)
        groups.append(item)
    preset = dict(view.get("preset") or {})
    return {
        "title": view.get("title") or "表单",
        "groups": groups,
        "fields": fields,
        "values": dict(preset),
        "refers": option_refers(fields),
        "request": {
            "model": bundle.uukey,
            "uukey": uukey,
            "logid": "",
            "using": using,
            "scene": scene or ("DETAIL" if uukey else "INSERT"),
        },
    }
