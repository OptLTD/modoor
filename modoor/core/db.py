from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from modoor.core.settings import Settings, get_settings


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
        Base.metadata.drop_all(engine)
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


def _ensure_columns(engine: Engine) -> None:
    stmts = (
        "ALTER TABLE doc_assets ADD COLUMN IF NOT EXISTS text_status VARCHAR(16) NOT NULL DEFAULT 'ready'",
        "ALTER TABLE doc_assets ADD COLUMN IF NOT EXISTS text_method VARCHAR(64) NOT NULL DEFAULT ''",
        "ALTER TABLE doc_assets ADD COLUMN IF NOT EXISTS text_error TEXT NOT NULL DEFAULT ''",
    )
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
