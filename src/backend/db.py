"""
SQLAlchemy database engine, session factory, and declarative base.
Supports SQLite for development/demo.  The engine URL is derived from
the application settings so swapping to PostgreSQL requires only an env-var change.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.backend.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _vercel_demo_database_url(url: str) -> str:
    """Use a writable copy of the bundled demo database in Vercel functions.

    Vercel deploys application files beneath ``/var/task`` as read-only. SQLite
    WAL mode creates ``-wal`` and ``-shm`` files beside the database, so opening
    the bundled database directly fails even for read requests. ``/tmp`` is the
    writable per-function filesystem Vercel provides.
    """
    if not os.environ.get("VERCEL") or settings.database_url or not url.startswith("sqlite:///"):
        return url

    bundled_path = Path(settings.database_path).resolve()
    if not bundled_path.is_file():
        return url

    runtime_path = Path(tempfile.gettempdir()) / bundled_path.name
    if not runtime_path.exists():
        shutil.copy2(bundled_path, runtime_path)
    return f"sqlite:///{runtime_path}"


def _make_engine(database_url: str | None = None):
    """
    Create the SQLAlchemy engine.

    SQLite-specific settings:
    - check_same_thread=False   required for FastAPI's thread-per-request model
    - WAL journal mode           improves concurrent read performance
    - foreign_keys enforcement   SQLite does not enforce FKs by default
    """
    url = database_url or settings.resolved_database_url
    if database_url is None:
        url = _vercel_demo_database_url(url)
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        echo=settings.is_development,   # SQL logging in dev mode
    )

    # Enable SQLite pragmas on every new connection
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = _make_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    """
    FastAPI dependency that yields a database session and ensures it is closed
    after the request, even if an exception is raised.

    Usage::

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(drop_existing: bool = False) -> None:
    """
    Create all tables defined by ORM models.

    Args:
        drop_existing: When True, drop all tables first (used by the seed script
                       to start from a clean state).
    """
    # Import models here to ensure all are registered with Base before
    # create_all / drop_all is called.
    import src.backend.models  # noqa: F401  — side-effect import

    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def verify_db_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
