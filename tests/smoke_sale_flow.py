"""End-to-end smoke without MCP host: create → confirm protocol → confirmed."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure package root on path when run as script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modoor.runtime.audit import write_audit  # noqa: E402
from modoor.runtime.auth import resolve_ctx  # noqa: E402
from modoor.runtime.confirmation import (  # noqa: E402
    issue_confirmation_token,
    needs_confirmation_payload,
    verify_confirmation_token,
)
from modoor.core.db import init_db, session_scope  # noqa: E402
from modules.sale import domain as sale_domain  # noqa: E402
from modoor.core.settings import Settings, get_settings  # noqa: E402


def main() -> None:
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("MODOOR_API_KEY", "dev-key-change-me")
    os.environ.setdefault("MODOOR_TENANT", "demo")
        os.environ.setdefault("MODOOR_CONFIRM_SECRET", "dev-confirm-secret-change-me")
    get_settings.cache_clear()

    settings = Settings()
    init_db(settings)
    ctx = resolve_ctx(settings)

    with session_scope() as session:
        created = sale_domain.create_order(
            session,
            ctx,
            partner_name="Acme Ltd",
            lines=[{"product_name": "Widget", "qty": 2, "unit_price": 10.5}],
            note="smoke",
        )
        write_audit(
            session,
            ctx=ctx,
            tool="sale.create_order",
            args={"partner_name": "Acme Ltd"},
            result_status="ok",
        )
        order_id = created["id"]
        assert created["state"] == "draft", created

        token, expires_at = issue_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool="sale.confirm_order",
            args={"order_id": order_id},
            ttl_seconds=settings.modoor_confirm_ttl_seconds,
        )
        pending = needs_confirmation_payload(
            token=token,
            expires_at=expires_at,
            tool="sale.confirm_order",
            summary={"order_id": order_id, "amount_total": created["amount_total"]},
            args={"order_id": order_id},
        )
        assert pending["status"] == "needs_confirmation"

        verify_confirmation_token(
            secret=settings.modoor_confirm_secret,
            ctx=ctx,
            tool="sale.confirm_order",
            args={"order_id": order_id},
            token=token,
        )
        confirmed = sale_domain.confirm_order(session, ctx, order_id)
        assert confirmed["state"] == "confirmed", confirmed
        write_audit(
            session,
            ctx=ctx,
            tool="sale.confirm_order",
            args={"order_id": order_id, "confirmation_token": "***"},
            result_status="ok",
        )

    print(json.dumps({"ok": True, "order_id": order_id, "state": "confirmed"}, indent=2))
    Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
