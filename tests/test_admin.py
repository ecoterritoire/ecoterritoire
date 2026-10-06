from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routes import admin as admin_routes
from lib import admin
from tests.helpers import CursorContext


def test_password_and_redis_helpers():
    encoded = admin.hash_password("secret", b"0123456789012345")
    assert admin.verify_password("secret", encoded)
    assert not admin.verify_password("wrong", encoded)
    assert not admin.verify_password("secret", "bad")

    client = MagicMock()
    client.get.side_effect = ["token", "4"]
    with patch("lib.admin._redis_client", return_value=client):
        assert admin.get_admin_session(1) == "token"
        admin.store_admin_session(1, "raw")
        assert admin._cached_usage(1) == 4

    client.get.side_effect = RuntimeError("offline")
    with patch("lib.admin._redis_client", return_value=client):
        assert admin.get_admin_session(1) is None
        admin.store_admin_session(1, "raw")
        assert admin._cached_usage(1) == 0


def test_database_helpers():
    cursor = MagicMock()
    cursor.fetchone.return_value = (1, "alice", "hash", "admin", True)
    with patch("lib.admin.get_db_cursor", return_value=CursorContext(cursor)):
        assert admin.find_user("alice")["username"] == "alice"

    cursor.fetchone.return_value = None
    with patch("lib.admin.get_db_cursor", return_value=CursorContext(cursor)):
        assert admin.find_user("missing") is None

    cursor.description = [
        ("id",), ("description",), ("created_at",),
        ("last_used_at",), ("is_active",), ("usage_count",),
    ]
    cursor.fetchall.return_value = [(1, "key", None, None, True, 2)]
    with patch("lib.admin.get_db_cursor", return_value=CursorContext(cursor)), patch(
        "lib.admin._cached_usage", return_value=3
    ):
        assert admin.list_api_tokens(10, 0)[0]["usage_count"] == 5

    cursor.fetchall.side_effect = [[(1, 2, True, None, None)]]
    cursor.fetchone.return_value = (3, 1)
    with patch("lib.admin.get_db_cursor", return_value=CursorContext(cursor)), patch(
        "lib.admin._cached_usage", return_value=1
    ):
        stats = admin.api_stats()
    assert stats == {
        "total_tokens": 1,
        "active_tokens": 1,
        "total_usage": 3,
        "created_last_7_days": 3,
        "used_last_24_hours": 1,
    }


def test_admin_routes():
    request = SimpleNamespace(
        url_for=lambda name, **params: f"/{name}/{params['path']}"
    )
    assert admin_routes.admin_page(request) is not None
    assert admin_routes.require_admin({"role": "admin"})["role"] == "admin"
    with pytest.raises(HTTPException):
        admin_routes.require_admin({"role": "user"})

    user = {"id": 1, "username": "alice", "role": "admin", "password_hash": "hash"}
    with patch("app.routes.admin.admin_db.find_user", return_value=user), patch(
        "app.routes.admin.admin_db.verify_password", return_value=True
    ), patch("app.routes.admin.create_admin_session"):
        response = admin_routes.admin_login(
            admin_routes.AdminLoginRequest(username="alice", password="secret")
        )
    assert response.username == "alice"

    with patch("app.routes.admin.admin_db.find_user", return_value=None):
        with pytest.raises(HTTPException):
            admin_routes.admin_login(
                admin_routes.AdminLoginRequest(username="alice", password="bad")
            )

    with patch("app.routes.admin.admin_db.list_api_tokens", return_value=[]), patch(
        "app.routes.admin.admin_db.api_stats", return_value={"total_tokens": 0}
    ):
        assert admin_routes.list_tokens({"role": "admin"})["data"] == []
        assert admin_routes.stats({"role": "admin"})["total_tokens"] == 0

    with patch("app.routes.admin.generate_new_token", return_value=("raw", {})):
        created = admin_routes.create_api_key(
            admin_routes.ApiKeyCreateRequest(description=" demo "),
            {"role": "admin"},
        )
    assert created.description == "demo"
