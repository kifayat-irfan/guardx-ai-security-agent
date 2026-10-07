"""SQLAlchemy engine + session factory."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"connect_timeout": 5}
    if url.startswith("sqlite"):
        connect_args = {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_postgres() -> dict:
    """Return a small status dict; never raises."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "up"}
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        return {"status": "down", "error": str(exc)[:200]}
