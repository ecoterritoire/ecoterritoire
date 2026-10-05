import hashlib
import hmac
import logging
import secrets
from typing import Any

from lib.config import settings
from lib.db import get_db_cursor

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
ADMIN_SESSION_PREFIX = "ecoterritoire:admin-session:"


def _redis_client():
    if redis is None:
        return None
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def get_admin_session(user_id: int) -> str | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        value = client.get(f"{ADMIN_SESSION_PREFIX}{user_id}")
        return value if isinstance(value, str) else None
    except Exception as exc:
        logger.warning("Redis admin session unavailable: %s", exc)
        return None


def store_admin_session(user_id: int, raw_token: str) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(
            f"{ADMIN_SESSION_PREFIX}{user_id}",
            settings.admin_session_ttl_seconds,
            raw_token,
        )
    except Exception as exc:
        logger.warning("Unable to store Redis admin session: %s", exc)


def _cached_usage(token_id: object) -> int:
    client = _redis_client()
    if client is None:
        return 0
    try:
        value = client.get(f"ecoterritoire:auth-usage:{token_id}")
        return int(value or 0)
    except Exception as exc:
        logger.warning("Redis usage statistics unavailable: %s", exc)
        return 0


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, 310_000
    )
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded_password.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def find_user(username: str) -> dict[str, Any] | None:
    query = """
        SELECT id, username, password_hash, role, is_active
        FROM app_users
        WHERE username = %s AND is_active = TRUE
    """
    with get_db_cursor() as cursor:
        cursor.execute(query, (username,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(
            zip(
                ("id", "username", "password_hash", "role", "is_active"),
                row,
            )
        )


def list_api_tokens(
    limit: int,
    offset: int,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            t.id, t.description, t.created_at, t.last_used_at,
            t.is_active, t.usage_count
        FROM api_tokens AS t
        WHERE t.user_id IS NULL
          AND t.description NOT LIKE 'Back-office login:%%'
          AND NULLIF(BTRIM(t.description), '') IS NOT NULL
    """
    if active_only:
        query += " AND t.is_active = TRUE"
    query += " ORDER BY t.created_at DESC, t.id DESC LIMIT %s OFFSET %s"

    with get_db_cursor() as cursor:
        cursor.execute(query, (limit, offset))
        columns = [description[0] for description in cursor.description]
        tokens = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for token in tokens:
            token["usage_count"] += _cached_usage(token["id"])
        return tokens


def api_stats() -> dict[str, int]:
    query = """
        SELECT id, usage_count, is_active, created_at, last_used_at
        FROM api_tokens
        WHERE user_id IS NULL
          AND description NOT LIKE 'Back-office login:%%'
          AND NULLIF(BTRIM(description), '') IS NOT NULL
    """
    with get_db_cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    now_query = """
        SELECT
            COUNT(*) FILTER (
                WHERE user_id IS NULL
                  AND description NOT LIKE 'Back-office login:%%'
                  AND NULLIF(BTRIM(description), '') IS NOT NULL
                  AND created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            ),
            COUNT(*) FILTER (
                WHERE user_id IS NULL
                  AND description NOT LIKE 'Back-office login:%%'
                  AND NULLIF(BTRIM(description), '') IS NOT NULL
                  AND last_used_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            )
        FROM api_tokens
    """
    with get_db_cursor() as cursor:
        cursor.execute(now_query)
        created_recently, used_recently = cursor.fetchone()
    return {
        "total_tokens": len(rows),
        "active_tokens": sum(1 for _, _, active, _, _ in rows if active),
        "total_usage": sum(
            int(usage_count) + _cached_usage(token_id)
            for token_id, usage_count, _, _, _ in rows
        ),
        "created_last_7_days": int(created_recently),
        "used_last_24_hours": int(used_recently),
    }
