"""Engine / session management. SQLite by default (zero setup), PostgreSQL via DATABASE_URL."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.logging_config import get_logger
from config.settings import settings

log = get_logger(__name__)
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = settings.database_url
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            if url.startswith("sqlite:///") and ":memory:" not in url:
                Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk_on(dbapi_conn, _):  # enforce foreign keys + better concurrency for the background analysis thread
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
        log.info("Database engine ready: %s", url.split("@")[-1] if "@" in url else url)
    return _engine


def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    from database.models import Base

    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    """Dispose the cached engine (used by tests that switch DATABASE_URL)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine, _SessionLocal = None, None


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
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
