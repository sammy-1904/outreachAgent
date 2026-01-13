"""Database session management for SQLite."""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .config import get_settings
from .models import Base


def _ensure_data_dir(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        # Expect format sqlite:///./data/outreach.db
        path_part = database_url.split("sqlite:///")[-1]
        db_path = Path(path_part)
        if db_path.parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_data_dir(settings.database_url)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
