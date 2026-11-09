import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "test_taskmanager.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests-only"

from fastapi.testclient import TestClient  # noqa: E402

from database import engine  # noqa: E402
from main import app  # noqa: E402


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_complete_mvp_flow() -> None:
    with TestClient(app) as client:
        register = client.post(
            "/auth/register",
            json={"email": "owner@example.com", "name": "Owner", "password": "password123"},
        )
        assert register.status_code == 201
        assert "password" not in register.text

        login = client.post(
            "/auth/login",
            json={"email": "owner@example.com", "password": "password123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = client.get("/me", headers=auth_header(token))
        assert me.status_code == 200
        assert me.json()["email"] == "owner@example.com"

        board = client.post(
            "/boards",
            json={"name": "Launch Board"},
            headers=auth_header(token),
        )
        assert board.status_code == 201
        board_id = board.json()["id"]

        member_register = client.post(
            "/auth/register",
            json={"email": "member@example.com", "name": "Member", "password": "password123"},
        )
        assert member_register.status_code == 201
        member_id = member_register.json()["id"]

        member_login = client.post(
            "/auth/login",
            json={"email": "member@example.com", "password": "password123"},
        )
        member_token = member_login.json()["access_token"]

        hidden_board = client.get(f"/boards/{board_id}", headers=auth_header(member_token))
        assert hidden_board.status_code == 404

        invited = client.post(
            f"/boards/{board_id}/members",
            json={"email": "member@example.com"},
            headers=auth_header(token),
        )
        assert invited.status_code == 201

        visible_board = client.get(f"/boards/{board_id}", headers=auth_header(member_token))
        assert visible_board.status_code == 200

        forbidden_invite = client.post(
            f"/boards/{board_id}/members",
            json={"email": "owner@example.com"},
            headers=auth_header(member_token),
        )
        assert forbidden_invite.status_code == 403

        task = client.post(
            f"/boards/{board_id}/tasks",
            json={"title": "Deploy API", "assignee_id": member_id},
            headers=auth_header(token),
        )
        assert task.status_code == 201
        assert task.json()["assignee_id"] == member_id
        task_id = task.json()["id"]

        moved = client.patch(
            f"/tasks/{task_id}",
            json={"status": "doing"},
            headers=auth_header(token),
        )
        assert moved.status_code == 200
        assert moved.json()["status"] == "doing"

        tasks = client.get(f"/boards/{board_id}/tasks", headers=auth_header(token))
        assert tasks.status_code == 200
        assert len(tasks.json()) == 1

        deleted = client.delete(f"/tasks/{task_id}", headers=auth_header(token))
        assert deleted.status_code == 204


def teardown_module() -> None:
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()

