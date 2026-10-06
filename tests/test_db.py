from unittest.mock import MagicMock, patch

import pytest

from lib import db
from tests.helpers import CursorContext


def test_token_and_session_operations():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        1, "hash", "description", "created", None, True, 2, "admin"
    )
    with patch("lib.db.get_db_cursor", return_value=CursorContext(cursor)):
        assert db.verify_token_hash("hash")["role"] == "admin"
        assert db.verify_admin_session("hash")["session"] is True
        db.create_admin_session("raw", 1, "tomorrow")
        db.revoke_admin_session("hash")

    cursor.fetchone.return_value = None
    with patch("lib.db.get_db_cursor", return_value=CursorContext(cursor)):
        assert db.verify_token_hash("missing") is None
        assert db.verify_admin_session("missing") is None

    cursor.fetchone.return_value = (2, "hash", "desc", "now", True, None)
    with patch("lib.db.get_db_cursor", return_value=CursorContext(cursor)):
        record = db.store_token("raw", "desc")
    assert record["id"] == 2

    with patch("lib.db.store_token", return_value={"created_at": "now"}):
        token, record = db.generate_new_token("desc")
    assert token.startswith("eco_")
    assert record["created_at"] == "now"


def test_pool_context_and_initialization():
    pool = MagicMock(closed=False)
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = CursorContext(cursor)
    pool.getconn.return_value = connection

    with patch("lib.db.pool.ThreadedConnectionPool", return_value=pool):
        db._connection_pool = None
        assert db.get_connection_pool() is pool
        with db.get_db_cursor() as current:
            assert current is cursor
        db.close_connection_pool()
        pool.closeall.assert_called_once()

    with patch("lib.db.get_db_cursor", return_value=CursorContext(cursor)):
        db.SEED_FILE = MagicMock(read_text=MagicMock(return_value="SELECT 1;"))
        db.init_db()
        assert cursor.execute.call_count == 2

    with patch("lib.db.SEED_FILE", new=MagicMock(
        read_text=MagicMock(side_effect=OSError("missing"))
    )):
        db.init_db()
    with patch("lib.db.get_db_cursor", side_effect=RuntimeError("offline")):
        db.init_db()


def test_error_paths():
    with patch("lib.db.psycopg2", None), patch("lib.db.pool", None):
        with pytest.raises(RuntimeError):
            db.get_connection_pool()

    cursor = MagicMock()
    cursor.fetchone.return_value = None
    with patch("lib.db.get_db_cursor", return_value=CursorContext(cursor)):
        with pytest.raises(RuntimeError):
            db.store_token("raw")

    with patch("lib.db.get_db_cursor", side_effect=RuntimeError("offline")):
        assert db.verify_token_hash("hash") is None
