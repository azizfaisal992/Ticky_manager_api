import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import Board, BoardMember, Task, User
from schemas import (
    BoardCreate,
    BoardRead,
    LoginRequest,
    MemberInvite,
    MemberRead,
    RegisterRequest,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TokenResponse,
    UserRead,
)
from security import create_access_token, decode_user_id, hash_password, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="Ticky Manager API",
    version="1.0.0",
    description="Boards and Kanban tasks for the Ticky Manager Android app.",
    lifespan=lifespan,
)

origins = [item.strip() for item in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

SessionDep = Annotated[Session, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


def normalized_email(email: str) -> str:
    return email.strip().lower()


def current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = decode_user_id(credentials.credentials)
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def get_board_for_member(session: Session, board_id: int, user_id: int) -> Board:
    membership = session.exec(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == user_id,
        )
    ).first()
    board = session.get(Board, board_id)
    if board is None or membership is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


def validate_assignee(session: Session, board_id: int, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    membership = session.exec(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == assignee_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=400, detail="Assignee is not a board member")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Ticky Manager API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: SessionDep) -> User:
    email = normalized_email(str(payload.email))
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    email = normalized_email(str(payload.email))
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/me", response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    return user


@app.get("/boards", response_model=list[BoardRead])
def list_boards(session: SessionDep, user: CurrentUser) -> list[Board]:
    statement = (
        select(Board)
        .join(BoardMember, BoardMember.board_id == Board.id)
        .where(BoardMember.user_id == user.id)
        .order_by(Board.created_at.desc())
    )
    return list(session.exec(statement).all())


@app.post("/boards", response_model=BoardRead, status_code=status.HTTP_201_CREATED)
def create_board(payload: BoardCreate, session: SessionDep, user: CurrentUser) -> Board:
    board = Board(name=payload.name.strip(), owner_id=user.id)
    session.add(board)
    session.flush()
    session.add(BoardMember(board_id=board.id, user_id=user.id, role="owner"))
    session.commit()
    session.refresh(board)
    return board


@app.get("/boards/{board_id}", response_model=BoardRead)
def read_board(board_id: int, session: SessionDep, user: CurrentUser) -> Board:
    return get_board_for_member(session, board_id, user.id)


@app.get("/boards/{board_id}/members", response_model=list[MemberRead])
def list_members(board_id: int, session: SessionDep, user: CurrentUser) -> list[MemberRead]:
    get_board_for_member(session, board_id, user.id)
    rows = session.exec(
        select(User, BoardMember.role)
        .join(BoardMember, BoardMember.user_id == User.id)
        .where(BoardMember.board_id == board_id)
        .order_by(User.name)
    ).all()
    return [MemberRead(id=member.id, email=member.email, name=member.name, role=role) for member, role in rows]


@app.post("/boards/{board_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def invite_member(
    board_id: int,
    payload: MemberInvite,
    session: SessionDep,
    user: CurrentUser,
) -> MemberRead:
    board = get_board_for_member(session, board_id, user.id)
    if board.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the board owner can invite members")

    invited = session.exec(
        select(User).where(User.email == normalized_email(str(payload.email)))
    ).first()
    if invited is None:
        raise HTTPException(status_code=404, detail="No registered user has this email")

    existing = session.exec(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == invited.id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already a board member")

    session.add(BoardMember(board_id=board_id, user_id=invited.id, role="member"))
    session.commit()
    return MemberRead(id=invited.id, email=invited.email, name=invited.name, role="member")


@app.get("/boards/{board_id}/tasks", response_model=list[TaskRead])
def list_tasks(board_id: int, session: SessionDep, user: CurrentUser) -> list[Task]:
    get_board_for_member(session, board_id, user.id)
    statement = (
        select(Task)
        .where(Task.board_id == board_id)
        .order_by(Task.status, Task.position, Task.created_at)
    )
    return list(session.exec(statement).all())


@app.post("/boards/{board_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    board_id: int,
    payload: TaskCreate,
    session: SessionDep,
    user: CurrentUser,
) -> Task:
    get_board_for_member(session, board_id, user.id)
    validate_assignee(session, board_id, payload.assignee_id)
    task = Task(board_id=board_id, **payload.model_dump())
    task.title = task.title.strip()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    get_board_for_member(session, task.board_id, user.id)

    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        validate_assignee(session, task.board_id, changes["assignee_id"])
    if isinstance(changes.get("title"), str):
        changes["title"] = changes["title"].strip()
    for field, value in changes.items():
        setattr(task, field, value)

    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: SessionDep, user: CurrentUser) -> Response:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    get_board_for_member(session, task.board_id, user.id)
    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

