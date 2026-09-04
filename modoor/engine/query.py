"""Query operator helpers (worth-compatible keys like basic.status:IN)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class QueryTerm:
    field: str
    op: str  # EQ|IN|NE|BTW|NIL|RCT|LIKE|GT|GTE|LT|LTE
    value: Any


def _recent_range(token: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    today = now.date()
    token = str(token or "").upper()
    if token == "CURRENT_MONTH":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    days = 30
    if token.endswith("_MONTH") or token.endswith("_MONTHS"):
        try:
            n = int(token.split("_")[1])
            days = 30 * max(n, 1)
        except Exception:  # noqa: BLE001
            days = 90
    elif token.endswith("_DAY") or token.endswith("_DAYS"):
        try:
            n = int(token.split("_")[1])
            days = max(n, 1)
        except Exception:  # noqa: BLE001
            days = 30
    elif "3_MONTH" in token:
        days = 90
    elif "1_MONTH" in token:
        days = 30
    start = today - timedelta(days=days)
    return start.isoformat(), today.isoformat()


def parse_query(query: dict[str, Any] | None) -> list[QueryTerm]:
    if not query:
        return []
    terms: list[QueryTerm] = []
    for raw_key, value in query.items():
        key = str(raw_key)
        if ":" in key:
            field, op = key.rsplit(":", 1)
            op = op.upper()
        elif isinstance(value, dict) and len(value) == 1:
            # allow { "basic.team_id": { "IN": [1, 2] } }
            op_key, nested_val = next(iter(value.items()))
            field, op, value = key, str(op_key).upper(), nested_val
        else:
            field, op = key, "EQ"
        if op == "RCT":
            a, b = _recent_range(str(value))
            terms.append(QueryTerm(field=field, op="BTW", value=[a, b]))
            continue
        terms.append(QueryTerm(field=field, op=op, value=value))
    return terms
