# Ticky Manager — API

The backend for **Ticky Manager**, a free, self-hosted Trello/Jira-style task manager.
It pairs with an Android app (Kotlin + Jetpack Compose) that lives in the `taskmanager-android` repo.

- **Stack:** Python + FastAPI, SQLModel, Argon2 password hashing, JWT auth
- **Database:** SQLite for local dev, PostgreSQL in production
- **Hosting target:** Render (free) + Supabase/Neon Postgres (free)
- **Scale:** ~10–15 users. No payments. Deliberately small.

## What it does

Users sign up and log in, create **boards**, invite other people to a board, and track
**tasks** inside each board across three statuses: `todo`, `doing`, `done`.

## Data model

```
User:        id, email, name, password_hash, created_at
Board:       id, name, owner_id, created_at
BoardMember: board_id, user_id, role ("owner" | "member")
Task:        id, board_id, title, description, status ("todo" | "doing" | "done"),
             assignee_id (nullable), position (int), created_at
```

## API endpoints (MVP)

| Method | Path                      | Purpose                              | Auth |
|--------|---------------------------|--------------------------------------|------|
| POST   | `/auth/register`          | Create a user                        | no   |
| POST   | `/auth/login`             | Log in, returns a JWT token          | no   |
| GET    | `/me`                     | The current user                     | yes  |
| GET    | `/boards`                 | Boards I'm a member of               | yes  |
| POST   | `/boards`                 | Create a board                       | yes  |
| GET    | `/boards/{id}`            | Board details                        | yes  |
| POST   | `/boards/{id}/members`    | Invite a user by email               | yes  |
| GET    | `/boards/{id}/tasks`      | Tasks in a board                     | yes  |
| POST   | `/boards/{id}/tasks`      | Create a task                        | yes  |
| PATCH  | `/tasks/{id}`             | Update title/status/assignee/position| yes  |
| DELETE | `/tasks/{id}`             | Delete a task                        | yes  |

## Local setup (Windows PowerShell)

Python 3.12 is recommended.

```powershell
cd taskmanager-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation or
`http://127.0.0.1:8000/health` for the deployment health check.

To run the automated MVP flow:

```powershell
python -m pytest -q
```

## Authentication

1. Register with `POST /auth/register`.
2. Log in with `POST /auth/login` and copy the returned `access_token`.
3. In `/docs`, click **Authorize** and paste the token.

Passwords are stored only as Argon2 hashes. Protected requests use an
`Authorization: Bearer <token>` header.

## Environment variables

Copy `.env.example` when running locally. The important production values are:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string from Supabase, Neon, or another managed provider |
| `SECRET_KEY` | Long random secret used to sign JWTs; never commit it |
| `ALLOWED_ORIGINS` | Comma-separated browser origins; Android clients do not need CORS |

SQLite is the local default. Production must use PostgreSQL because free web
services may erase files stored on their local filesystem.

## Deploy to Render

The included `render.yaml` defines the web service, health check, start command,
and environment variables.

1. Push this `taskmanager-api` directory to a GitHub repository.
2. Create a PostgreSQL database in Supabase or Neon and copy its connection URL.
3. In Render, choose **New → Blueprint** and select the repository.
4. Enter the PostgreSQL URL when Render asks for `DATABASE_URL`.
5. Render generates `SECRET_KEY` automatically from `render.yaml`.
6. After deployment, open `https://YOUR-SERVICE.onrender.com/health` and verify
   that it returns `{"status":"ok"}`.
7. Open `/docs`, register a user, log in, authorize, then create a board and task.

Do not put `DATABASE_URL`, `SECRET_KEY`, passwords, or access tokens in GitHub.

## Status

The deployable API foundation is complete: authentication, boards, membership,
task CRUD, SQLite/PostgreSQL switching, tests, and Render configuration.
The Android client is the next phase.
