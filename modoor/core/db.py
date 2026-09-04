from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from modoor.core.settings import Settings, get_settings

# Old plural table names → singular. Rename before create_all so local DBs keep data.
TABLE_RENAMES: tuple[tuple[str, str], ...] = (
    ("base_tenants", "base_tenant"),
    ("base_apps", "base_app"),
    ("base_logins", "base_login"),
    ("base_teams", "base_team"),
    ("base_users", "base_user"),
    ("base_roles", "base_role"),
    ("sale_orders", "sale_order"),
    ("sale_order_lines", "sale_order_line"),
    ("wiki_projects", "wiki_project"),
    ("wiki_pages", "wiki_page"),
    ("skill_items", "skill_item"),
    ("doc_assets", "doc_asset"),
    ("audit_logs", "audit_log"),
    ("module_installs", "module_install"),
)


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db(settings: Settings | None = None, *, recreate: bool = False) -> Engine:
    global _engine, _SessionLocal
    reset_engine()
    settings = settings or get_settings()
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)

    # Ensure model modules register tables on Base.metadata
    from modoor.platform import module_state as _module_state  # noqa: F401
    from modoor.platform.loader import load_module_domains
    from modoor.runtime import audit as _audit  # noqa: F401
    from modoor.runtime import jobs as _jobs  # noqa: F401

    load_module_domains(settings)

    if recreate:
        with engine.begin() as conn:
            _drop_fks_on_column(conn, "base_user", "login_id")
            _drop_fks_on_column(conn, "base_user", "base_id")
        Base.metadata.drop_all(engine)
        _drop_legacy_tables(engine)
    else:
        _rename_legacy_tables(engine)
    Base.metadata.create_all(engine)
    _ensure_columns(engine)
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _drop_legacy_tables(engine: Engine) -> None:
    with engine.begin() as conn:
        for old, _new in TABLE_RENAMES:
            conn.execute(text(f'DROP TABLE IF EXISTS "{old}" CASCADE'))


def _rename_legacy_tables(engine: Engine) -> None:
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    with engine.begin() as conn:
        for old, new in TABLE_RENAMES:
            if old in existing and new not in existing:
                conn.execute(text(f'ALTER TABLE "{old}" RENAME TO "{new}"'))
                existing.discard(old)
                existing.add(new)


def _table_columns(conn, table: str) -> dict[str, str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
            """
        ),
        {"t": table},
    ).all()
    return {str(name): str(dtype) for name, dtype in rows}


def _table_exists(conn, table: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :t
                """
            ),
            {"t": table},
        ).scalar()
    )


def _ensure_unique_index(conn, name: str, table: str, columns: str) -> None:
    conn.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns})'))


def _ensure_partial_unique_index(conn, name: str, table: str, columns: str, where: str) -> None:
    conn.execute(
        text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns}) WHERE {where}'
        )
    )


def _ensure_smallint_state(conn, table: str, *, sale: bool = False) -> None:
    if not _table_exists(conn, table):
        return
    cols = _table_columns(conn, table)
    default = 0 if sale else 1
    if "state" not in cols:
        conn.execute(
            text(
                f'ALTER TABLE "{table}" ADD COLUMN state SMALLINT NOT NULL DEFAULT {default}'
            )
        )
        return
    if cols["state"] in ("smallint", "integer"):
        return
    if sale:
        using = """
            CASE
              WHEN lower(state::text) IN ('confirmed', '1') THEN 1
              ELSE 0
            END
        """
    else:
        using = """
            CASE
              WHEN lower(state::text) IN ('active', '1', 'true', 'on') THEN 1
              ELSE 0
            END
        """
    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN state DROP DEFAULT'))
    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN state TYPE SMALLINT USING ({using})'))
    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN state SET DEFAULT {default}'))
    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN state SET NOT NULL'))


def _backfill_uukey(conn, table: str, prefix: str) -> None:
    cols = _table_columns(conn, table)
    if not cols:
        return
    if "uukey" not in cols:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN uukey VARCHAR(32)'))
    conn.execute(
        text(
            f"""
            UPDATE "{table}"
            SET uukey = :prefix || lpad(id::text, 5, '0')
            WHERE uukey IS NULL OR btrim(uukey) = ''
            """
        ),
        {"prefix": prefix},
    )


def _user_bind_col(cols: dict[str, str]) -> str:
    if "base_id" in cols:
        return "base_id"
    return "login_id"


def _drop_fks_on_column(conn, table: str, column: str) -> None:
    rows = conn.execute(
        text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
            WHERE c.contype = 'f' AND t.relname = :t AND a.attname = :c
            """
        ),
        {"t": table, "c": column},
    ).all()
    for (name,) in rows:
        conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'))


def _migrate_identity(conn) -> None:
    if not _table_exists(conn, "base_user"):
        return
    cols = _table_columns(conn, "base_user")
    bind = _user_bind_col(cols)
    if bind not in cols:
        conn.execute(text(f"ALTER TABLE base_user ADD COLUMN {bind} INTEGER"))
        cols = _table_columns(conn, "base_user")
    if "username" in cols:
        users = conn.execute(
            text(
                f"""
                SELECT id, username, password
                FROM base_user
                WHERE {bind} IS NULL
                """
            )
        ).mappings().all()
        for user in users:
            uname = str(user["username"] or "").strip().lower() or f"user{user['id']}"
            login = conn.execute(
                text("SELECT id FROM base_login WHERE username = :u"),
                {"u": uname},
            ).first()
            if login is None:
                login_cols = _table_columns(conn, "base_login")
                user_cols = _table_columns(conn, "base_user")
                realname = ""
                tenant = None
                extra_cols = [c for c in ("realname", "name", "tenant") if c in user_cols]
                if extra_cols:
                    extra = conn.execute(
                        text(
                            f"SELECT {', '.join(extra_cols)} FROM base_user WHERE id = :id"
                        ),
                        {"id": user["id"]},
                    ).mappings().first()
                    if extra:
                        realname = str(extra.get("realname") or extra.get("name") or "")
                        tenant = extra.get("tenant")
                if "realname" in login_cols and "current" in login_cols:
                    conn.execute(
                        text(
                            """
                            INSERT INTO base_login
                                (username, password, realname, current, created_at, updated_at)
                            VALUES (:u, :p, :n, :t, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"u": uname, "p": user["password"], "n": realname, "t": tenant},
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO base_login (username, password, created_at, updated_at)
                            VALUES (:u, :p, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"u": uname, "p": user["password"]},
                    )
                login = conn.execute(
                    text("SELECT id FROM base_login WHERE username = :u"),
                    {"u": uname},
                ).first()
            if login is not None:
                conn.execute(
                    text(f"UPDATE base_user SET {bind} = :lid WHERE id = :id"),
                    {"lid": login[0], "id": user["id"]},
                )
        conn.execute(text("ALTER TABLE base_user DROP COLUMN IF EXISTS username"))
        conn.execute(text("ALTER TABLE base_user DROP COLUMN IF EXISTS password"))

    leftover = conn.execute(
        text(f"SELECT 1 FROM base_user WHERE {bind} IS NULL LIMIT 1")
    ).scalar()
    if leftover is not None:
        return
    nullable = conn.execute(
        text(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'base_user'
              AND column_name = :c
            """
        ),
        {"c": bind},
    ).scalar()
    if nullable == "YES":
        conn.execute(text(f"ALTER TABLE base_user ALTER COLUMN {bind} SET NOT NULL"))


def _rename_login_id_to_base_id(conn) -> None:
    if not _table_exists(conn, "base_user"):
        return
    cols = _table_columns(conn, "base_user")
    _drop_fks_on_column(conn, "base_user", "login_id")
    _drop_fks_on_column(conn, "base_user", "base_id")
    if "login_id" in cols and "base_id" not in cols:
        conn.execute(text("ALTER TABLE base_user RENAME COLUMN login_id TO base_id"))
    elif "login_id" in cols and "base_id" in cols:
        conn.execute(
            text(
                "UPDATE base_user SET base_id = login_id WHERE base_id IS NULL AND login_id IS NOT NULL"
            )
        )
        conn.execute(text("ALTER TABLE base_user DROP COLUMN IF EXISTS login_id"))
    _drop_fks_on_column(conn, "base_user", "base_id")


def _ensure_login_columns(conn) -> None:
    if not _table_exists(conn, "base_login"):
        return
    cols = _table_columns(conn, "base_login")
    if "realname" not in cols:
        conn.execute(
            text(
                "ALTER TABLE base_login ADD COLUMN realname VARCHAR(256) NOT NULL DEFAULT ''"
            )
        )
    if "current" not in cols:
        conn.execute(text("ALTER TABLE base_login ADD COLUMN current INTEGER"))


def _backfill_login_profile(conn) -> None:
    if not _table_exists(conn, "base_login") or not _table_exists(conn, "base_user"):
        return
    user_cols = _table_columns(conn, "base_user")
    bind = _user_bind_col(user_cols)
    if bind not in user_cols:
        return
    if "realname" in user_cols:
        conn.execute(
            text(
                f"""
                UPDATE base_login l
                SET realname = s.realname
                FROM (
                    SELECT DISTINCT ON ({bind}) {bind} AS bind_id, realname
                    FROM base_user
                    WHERE {bind} IS NOT NULL
                      AND realname IS NOT NULL
                      AND btrim(realname) <> ''
                    ORDER BY {bind}, id
                ) s
                WHERE l.id = s.bind_id
                  AND btrim(COALESCE(l.realname, '')) = ''
                """
            )
        )
        conn.execute(text("ALTER TABLE base_user DROP COLUMN IF EXISTS realname"))
        user_cols = _table_columns(conn, "base_user")
    if "tenant" in user_cols:
        conn.execute(
            text(
                f"""
                UPDATE base_login l
                SET current = s.tenant
                FROM (
                    SELECT DISTINCT ON ({bind}) {bind} AS bind_id, tenant
                    FROM base_user
                    WHERE {bind} IS NOT NULL
                    ORDER BY {bind}, id
                ) s
                WHERE l.id = s.bind_id
                  AND l.current IS NULL
                """
            )
        )


def _ensure_columns(engine: Engine) -> None:
    with engine.begin() as conn:
        if _table_exists(conn, "doc_asset"):
            conn.execute(
                text(
                    "ALTER TABLE doc_asset ADD COLUMN IF NOT EXISTS text_status VARCHAR(16) NOT NULL DEFAULT 'ready'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE doc_asset ADD COLUMN IF NOT EXISTS text_method VARCHAR(64) NOT NULL DEFAULT ''"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE doc_asset ADD COLUMN IF NOT EXISTS text_error TEXT NOT NULL DEFAULT ''"
                )
            )

        if _table_exists(conn, "base_user"):
            cols = _table_columns(conn, "base_user")
            if "utime" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE base_user ADD COLUMN utime TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP"
                    )
                )
            _backfill_uukey(conn, "base_user", "USER")
            _ensure_smallint_state(conn, "base_user")
            _ensure_login_columns(conn)
            _migrate_identity(conn)
            _backfill_login_profile(conn)
            _rename_login_id_to_base_id(conn)
            cols = _table_columns(conn, "base_user")
            if "name" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE base_user ADD COLUMN name VARCHAR(256) NOT NULL DEFAULT ''"
                    )
                )
            if "phone" not in cols:
                conn.execute(text("ALTER TABLE base_user ADD COLUMN phone VARCHAR(32)"))
            if "remark" not in cols:
                conn.execute(text("ALTER TABLE base_user ADD COLUMN remark TEXT"))
            conn.execute(
                text(
                    """
                    UPDATE base_user u
                    SET name = l.realname
                    FROM base_login l
                    WHERE l.id = u.base_id
                      AND btrim(COALESCE(u.name, '')) = ''
                      AND btrim(COALESCE(l.realname, '')) <> ''
                    """
                )
            )
            _ensure_unique_index(
                conn, "uq_base_user_tenant_uukey", "base_user", "tenant, uukey"
            )
            _ensure_unique_index(
                conn, "uq_base_user_tenant_base", "base_user", "tenant, base_id"
            )
            _ensure_partial_unique_index(
                conn,
                "uq_base_user_tenant_email",
                "base_user",
                "tenant, lower(btrim(email))",
                "email IS NOT NULL AND btrim(email) <> ''",
            )
            _ensure_partial_unique_index(
                conn,
                "uq_base_user_tenant_phone",
                "base_user",
                "tenant, lower(btrim(phone))",
                "phone IS NOT NULL AND btrim(phone) <> ''",
            )

        if _table_exists(conn, "base_team"):
            cols = _table_columns(conn, "base_team")
            if "utime" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE base_team ADD COLUMN utime TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP"
                    )
                )
            _backfill_uukey(conn, "base_team", "TM")
            _ensure_smallint_state(conn, "base_team")
            _ensure_unique_index(
                conn, "uq_base_team_tenant_uukey", "base_team", "tenant, uukey"
            )

        _ensure_smallint_state(conn, "sale_order", sale=True)
