"""EngineService — TableSchema / Search / Input / Upsert (worth wire)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from modoor.core.ctx import Ctx
from modoor.core.errors import AppError
from modoor.engine.adapters import get_adapter
from modoor.engine.project import build_source, project_input, project_table
from modoor.engine.registry import clear_bundle_cache, get_bundle


class EngineService:
    def table_schema(self, body: dict[str, Any]) -> dict[str, Any]:
        model = str(body.get("model") or "").strip()
        if not model:
            raise AppError("validation_error", "model required")
        using = str(body.get("using") or "default")
        scene = str(body.get("scene") or "SEARCH")
        page = int(body.get("page") or 1)
        size = int(body.get("size") or 50)
        bundle = get_bundle(model)
        table = project_table(
            bundle,
            using=using,
            scene=scene,
            page=page,
            size=size,
            query=body.get("query") if isinstance(body.get("query"), dict) else None,
            order=body.get("order") if isinstance(body.get("order"), dict) else None,
        )
        return {
            "model": model,
            "using": using,
            "scene": scene,
            "table": table,
            "source": build_source(bundle),
        }

    def input_schema(
        self,
        session: Session,
        ctx: Ctx,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(body.get("model") or "").strip()
        if not model:
            raise AppError("validation_error", "model required")
        using = str(body.get("using") or "default")
        uukey = str(body.get("uukey") or "").strip()
        scene = str(body.get("scene") or ("DETAIL" if uukey else "INSERT"))
        bundle = get_bundle(model)
        inp = project_input(bundle, using=using, scene=scene, uukey=uukey)
        if uukey:
            adapter = get_adapter(model)
            values = adapter.get_values(session, ctx, uukey)
            if values is None:
                raise AppError("not_found", f"record not found: {uukey}")
            # merge preset under real values
            merged = dict(inp.get("values") or {})
            merged.update(values)
            inp["values"] = merged
        return {
            "model": model,
            "using": using,
            "scene": scene,
            "input": inp,
        }

    def search(
        self,
        session: Session,
        ctx: Ctx,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(body.get("model") or "").strip()
        if not model:
            raise AppError("validation_error", "model required")
        using = str(body.get("using") or "default")
        scene = str(body.get("scene") or "SEARCH")
        page = int(body.get("page") or 1)
        size = int(body.get("size") or 50)
        bundle = get_bundle(model)
        table = project_table(
            bundle,
            using=using,
            scene=scene,
            page=page,
            size=size,
            query=body.get("query") if isinstance(body.get("query"), dict) else None,
            order=body.get("order") if isinstance(body.get("order"), dict) else None,
        )
        req = table["request"]
        # request query merges view defaults; caller query already merged in project
        query = dict(req.get("query") or {})
        if isinstance(body.get("query"), dict):
            query.update(body["query"])
        order = body.get("order") if isinstance(body.get("order"), dict) else req.get("order")
        field_keys = [f["uukey"] for f in table["fields"]]
        adapter = get_adapter(model)
        values, count, totals = adapter.search(
            session,
            ctx,
            query=query,
            order=order,
            page=page,
            size=size,
            field_keys=field_keys,
        )
        refers = dict(table.get("refers") or {})
        return {
            "page": page,
            "size": size,
            "count": count,
            "refers": refers,
            "totals": totals,
            "values": values,
        }

    def upsert(
        self,
        session: Session,
        ctx: Ctx,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(body.get("model") or "").strip()
        if not model:
            raise AppError("validation_error", "model required")
        batch = body.get("batch")
        if not isinstance(batch, list) or not batch:
            raise AppError("validation_error", "batch required")
        # validate model exists
        get_bundle(model)
        adapter = get_adapter(model)
        records = adapter.upsert(session, ctx, batch)
        return {"records": records}

    def delete(
        self,
        session: Session,
        ctx: Ctx,
        *,
        model: str,
        keys: list[str],
    ) -> dict[str, Any]:
        get_bundle(model)
        adapter = get_adapter(model)
        adapter.delete_keys(session, ctx, keys)
        return {"ok": True}


@lru_cache
def get_engine() -> EngineService:
    return EngineService()


def reload_engine_caches() -> None:
    clear_bundle_cache()
    get_engine.cache_clear()
