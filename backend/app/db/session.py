"""SQLAlchemy engine & session factory."""

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Lazy initialization - only create engine when first needed
_engine: Optional[object] = None
_SessionLocal: Optional[sessionmaker] = None  # type: ignore[type-arg]


def get_engine():
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal


# For backward compatibility, expose as module-level vars
# but they will initialize lazily on first access
@property  # type: ignore[misc]
def engine():  # type: ignore[misc]
    """Lazy-loaded engine."""
    return get_engine()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Session:  # type: ignore[misc]
    """FastAPI dependency — yields a DB session and closes it after the request."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()
