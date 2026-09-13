"""
SafeVision AI — Database Engine & Session Management

Sets up SQLAlchemy async-compatible engine and session factory.
All sessions are scoped and closed properly via dependency injection.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    All models inherit from this — keeps one metadata registry.
    """
    pass


def get_engine():
    """Create the SQLAlchemy engine from config."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,      # Verify connections before use
        pool_size=10,             # Connection pool size
        max_overflow=20,          # Extra connections beyond pool_size
        pool_recycle=300,         # Recycle connections every 5 min
        echo=settings.debug,     # Log SQL in debug mode only
    )


# Engine singleton — created once on module import
engine = get_engine()

# Session factory — produces new Session instances
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    """
    FastAPI dependency that yields a database session.
    Ensures the session is always closed after the request,
    even if an exception occurs.

    Usage in endpoints:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
