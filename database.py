import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./taskmanager.db")
    # Some hosting providers still expose the legacy scheme name.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=not IS_SQLITE,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

