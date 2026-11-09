from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    name: str = Field(max_length=100)
    password_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class Board(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class BoardMember(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("board_id", "user_id"),)

    board_id: int = Field(foreign_key="board.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role: str = Field(default="member", max_length=20)


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(foreign_key="board.id", index=True)
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=4000)
    status: str = Field(default="todo", max_length=20, index=True)
    assignee_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)

