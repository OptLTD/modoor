"""Doc domain — unstructured asset warehouse for AI + human preview."""

from __future__ import annotations

import json
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from modoor.core.ctx import Ctx
from modoor.core.db import Base
from modoor.core.errors import AppError
from modoor.core.settings import get_settings
from modules.doc.storage import BlobStore, get_blob_store

_TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".html", ".htm", ".xml"}
_MAX_TEXT_CHARS = 500_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _safe_filename(name: str) -> str:
    base = Path(name or "file").name
    cleaned = re.sub(r"[^\w.\-()+ ]+", "_", base, flags=re.UNICODE).strip("._ ")
    return (cleaned or "file")[:180]


def _guess_mime(filename: str, declared: str | None = None) -> str:
    if declared and declared.strip() and declared != "application/octet-stream":
        return declared.strip()
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _dumps_tags(tags: list[str] | None) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        t = str(raw or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        cleaned.append(t[:64])
    return json.dumps(cleaned, ensure_ascii=False)


def _loads_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def extract_text(filename: str, data: bytes, mime: str) -> str:
    """Best-effort plain text for search / AI. Preview still uses original bytes."""
    ext = Path(filename).suffix.lower()
    mime_l = (mime or "").lower()

    if ext in _TEXT_EXTS or mime_l.startswith("text/") or mime_l in (
        "application/json",
        "application/xml",
        "application/javascript",
    ):
        for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
            try:
                return data.decode(enc)[:_MAX_TEXT_CHARS]
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")[:_MAX_TEXT_CHARS]

    if ext == ".docx" or mime_l.endswith(
        "officedocument.wordprocessingml.document"
    ):
        try:
            import zipfile
            from io import BytesIO
            from xml.etree import ElementTree as ET

            with zipfile.ZipFile(BytesIO(data)) as zf:
                xml = zf.read("word/document.xml")
            root = ET.fromstring(xml)
            texts = [
                (node.text or "")
                for node in root.iter()
                if node.tag.endswith("}t") and node.text
            ]
            return "\n".join(texts)[:_MAX_TEXT_CHARS]
        except Exception:  # noqa: BLE001
            return ""

    if ext in (".xlsx", ".xls") or "spreadsheetml" in mime_l:
        try:
            import zipfile
            from io import BytesIO
            from xml.etree import ElementTree as ET

            if ext == ".xls":
                return ""
            parts: list[str] = []
            with zipfile.ZipFile(BytesIO(data)) as zf:
                shared: list[str] = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    ss = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for si in ss:
                        texts = [
                            (t.text or "")
                            for t in si.iter()
                            if t.tag.endswith("}t")
                        ]
                        shared.append("".join(texts))
                for name in zf.namelist():
                    if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                        continue
                    sheet = ET.fromstring(zf.read(name))
                    for c in sheet.iter():
                        if not c.tag.endswith("}c"):
                            continue
                        v = next((ch for ch in list(c) if ch.tag.endswith("}v")), None)
                        if v is None or v.text is None:
                            continue
                        if c.get("t") == "s":
                            try:
                                parts.append(shared[int(v.text)])
                            except (ValueError, IndexError):
                                parts.append(v.text)
                        else:
                            parts.append(v.text)
            return "\n".join(parts)[:_MAX_TEXT_CHARS]
        except Exception:  # noqa: BLE001
            return ""

    if ext == ".pptx" or "presentationml" in mime_l:
        try:
            import zipfile
            from io import BytesIO
            from xml.etree import ElementTree as ET

            parts: list[str] = []
            with zipfile.ZipFile(BytesIO(data)) as zf:
                for name in sorted(zf.namelist()):
                    if not name.startswith("ppt/slides/slide") or not name.endswith(".xml"):
                        continue
                    root = ET.fromstring(zf.read(name))
                    for node in root.iter():
                        if node.tag.endswith("}t") and node.text:
                            parts.append(node.text)
            return "\n".join(parts)[:_MAX_TEXT_CHARS]
        except Exception:  # noqa: BLE001
            return ""

    return ""


class DocAsset(Base):
    __tablename__ = "doc_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(32), default="local")  # storage backend
    name: Mapped[str] = mapped_column(String(1024), default="")  # object key
    tags: Mapped[str] = mapped_column(Text, default="[]")
    text: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


def _asset_dict(row: DocAsset, *, include_text: bool = True, text_limit: int | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": row.id,
        "tenant": row.tenant,
        "team_id": row.team_id,
        "title": row.title,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "type": row.type,
        "name": row.name,
        "tags": _loads_tags(row.tags),
        "note": row.note or "",
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "has_text": bool((row.text or "").strip()),
        "ext": Path(row.filename or "").suffix.lower().lstrip("."),
    }
    if include_text:
        body = row.text or ""
        if text_limit is not None and len(body) > text_limit:
            data["text"] = body[:text_limit]
            data["text_truncated"] = True
        else:
            data["text"] = body
            data["text_truncated"] = False
    return data


def _scope(ctx: Ctx):
    return select(DocAsset).where(DocAsset.tenant == ctx.tenant, DocAsset.team_id == ctx.team_id)


def _get_asset(session: Session, ctx: Ctx, asset_id: str) -> DocAsset:
    row = session.get(DocAsset, asset_id)
    if row is None or row.tenant != ctx.tenant:
        raise AppError("not_found", "Doc asset not found")
    if row.team_id != ctx.team_id:
        raise AppError("permission_denied", "Asset outside team scope")
    return row


def _store_for_row(row: DocAsset, settings=None) -> BlobStore:
    """Use current configured store; type on row is a snapshot for future multi-backend reads."""
    settings = settings or get_settings()
    store = get_blob_store(settings)
    # If row was written with another backend, refuse silent mismatch for now
    if row.type and row.type != store.backend:
        raise AppError(
            "not_implemented",
            f"asset stored on '{row.type}' but current MODOOR_DOC_STORAGE is '{store.backend}'",
        )
    return store


def create_asset(
    session: Session,
    ctx: Ctx,
    *,
    filename: str,
    data: bytes,
    title: str | None = None,
    mime_type: str | None = None,
    tags: list[str] | None = None,
    note: str = "",
    text: str | None = None,
) -> dict[str, Any]:
    if not data and text is None:
        raise AppError("validation_error", "file content is required")
    settings = get_settings()
    store = get_blob_store(settings)
    asset_id = _new_id()
    safe = _safe_filename(filename or "file")
    mime = _guess_mime(safe, mime_type)
    blob = data if data else (text or "").encode("utf-8")
    object_name = f"{ctx.tenant}/{asset_id}/{safe}"
    store.put(object_name, blob, content_type=mime)
    extracted = text if text is not None else extract_text(safe, blob, mime)
    row = DocAsset(
        id=asset_id,
        tenant=ctx.tenant,
        team_id=ctx.team_id,
        title=(title or Path(safe).stem or "Untitled").strip()[:512],
        filename=safe,
        mime_type=mime,
        size_bytes=len(blob),
        type=store.backend,
        name=object_name,
        tags=_dumps_tags(tags),
        text=(extracted or "")[:_MAX_TEXT_CHARS],
        note=(note or "").strip(),
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return _asset_dict(row)


def create_text_asset(
    session: Session,
    ctx: Ctx,
    *,
    title: str,
    text: str,
    tags: list[str] | None = None,
    note: str = "",
    filename: str | None = None,
) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise AppError("validation_error", "title is required")
    body = text or ""
    fname = _safe_filename(filename or f"{title}.txt")
    return create_asset(
        session,
        ctx,
        filename=fname,
        data=body.encode("utf-8"),
        title=title,
        mime_type="text/plain; charset=utf-8",
        tags=tags,
        note=note,
        text=body,
    )


def list_assets(
    session: Session,
    ctx: Ctx,
    *,
    q: str | None = None,
    tag: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = min(max(int(limit or 100), 1), 500)
    rows = list(session.scalars(_scope(ctx).order_by(DocAsset.updated_at.desc())))
    needle = (q or "").strip().lower()
    tag_needle = (tag or "").strip()
    items: list[dict[str, Any]] = []
    for row in rows:
        tags = _loads_tags(row.tags)
        if tag_needle and tag_needle not in tags:
            continue
        if needle:
            blob = " ".join(
                [
                    row.title or "",
                    row.filename or "",
                    " ".join(tags),
                    row.note or "",
                    row.text or "",
                ]
            ).lower()
            if needle not in blob:
                continue
        items.append(_asset_dict(row, include_text=False))
        if len(items) >= limit:
            break
    return {"items": items, "count": len(items)}


def get_asset(
    session: Session,
    ctx: Ctx,
    *,
    asset_id: str,
    include_text: bool = True,
    text_limit: int | None = None,
) -> dict[str, Any]:
    return _asset_dict(
        _get_asset(session, ctx, asset_id),
        include_text=include_text,
        text_limit=text_limit,
    )


def get_asset_bytes(session: Session, ctx: Ctx, *, asset_id: str) -> tuple[DocAsset, bytes]:
    row = _get_asset(session, ctx, asset_id)
    if not row.name:
        raise AppError("not_found", "asset has no stored blob")
    data = _store_for_row(row).get(row.name)
    return row, data


def update_asset(
    session: Session,
    ctx: Ctx,
    *,
    asset_id: str,
    title: str | None = None,
    tags: list[str] | None = None,
    note: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    row = _get_asset(session, ctx, asset_id)
    if title is None and tags is None and note is None and text is None:
        raise AppError("validation_error", "provide title, tags, note, and/or text")
    if title is not None:
        title = title.strip()
        if not title:
            raise AppError("validation_error", "title is required")
        row.title = title[:512]
    if tags is not None:
        row.tags = _dumps_tags(tags)
    if note is not None:
        row.note = note.strip()
    if text is not None:
        row.text = text[:_MAX_TEXT_CHARS]
    row.updated_by = ctx.user_id
    row.updated_at = _now()
    session.flush()
    return _asset_dict(row)


def delete_asset(session: Session, ctx: Ctx, *, asset_id: str) -> dict[str, Any]:
    row = _get_asset(session, ctx, asset_id)
    payload = _asset_dict(row, include_text=False)
    name = row.name
    backend = row.type
    session.delete(row)
    session.flush()
    if name:
        try:
            settings = get_settings()
            store = get_blob_store(settings)
            if backend == store.backend:
                store.delete(name)
        except AppError:
            pass
    return {"deleted": True, "asset": payload}


def list_tags(session: Session, ctx: Ctx) -> dict[str, Any]:
    rows = list(session.scalars(_scope(ctx)))
    counts: dict[str, int] = {}
    for row in rows:
        for t in _loads_tags(row.tags):
            counts[t] = counts.get(t, 0) + 1
    items = [{"tag": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    return {"items": items, "count": len(items)}
