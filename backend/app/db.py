"""Database engine and sessions (Aiven for PostgreSQL in every shared environment)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

_INIT_LOCK_ID = 727_001  # any constant; serializes schema creation across processes


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: Aiven closes idle connections; reconnect transparently.
    return create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True, pool_size=5)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session


def init_db() -> None:
    """Create extensions and tables. Safe to call from the API and the worker at once.

    Hackathon trade-off: `create_all` adds new tables but never alters existing ones.
    Add a column? Drop the table on your local DB, or move to Alembic when it hurts.
    """
    with get_engine().begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _INIT_LOCK_ID})
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        Base.metadata.create_all(conn)
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS elements_text_trgm ON elements "
                "USING gin ((coalesce(label, '') || ' ' || coalesce(name, '') || ' ' "
                "|| coalesce(text, '')) gin_trgm_ops)"
            )
        )
