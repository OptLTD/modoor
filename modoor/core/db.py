from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from modoor.core.settings import Settings, get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _sqlite_fk(dbapi_conn, connection_record) -> None:  # noqa: ARG001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db(settings: Settings | None = None) -> Engine:
    global _engine, _SessionLocal
    settings = settings or get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _sqlite_fk)

    # Ensure model modules register tables on Base.metadata
    from modoor.platform import module_state as _module_state  # noqa: F401
    from modoor.platform.loader import load_module_domains
    from modoor.runtime import audit as _audit  # noqa: F401

    load_module_domains(settings)

    Base.metadata.create_all(engine)
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
