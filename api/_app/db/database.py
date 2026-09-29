"""SQLAlchemy engine/session wired to DATABASE_URL (Postgres in production).

Vercel serverless functions are short-lived and can spawn many concurrent
invocations, so the pool is kept intentionally small and pre-ping is enabled to
avoid handing out dead connections after a cold start.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from .models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Configure a Postgres connection string "
                "(see .env.example)."
            )
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_size=3,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=280,
        )
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every cold start."""
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Session:
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
