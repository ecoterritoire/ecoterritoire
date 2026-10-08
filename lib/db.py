import hashlib
import logging
import os
import secrets
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from typing import Any

from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extensions import cursor as Cursor
except ImportError:
    psycopg2 = None  # type: ignore
    pool = None  # type: ignore
    Cursor = Any  # type: ignore

logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5433/ecoterritoire",
)

_connection_pool: pool.ThreadedConnectionPool | None = None
SEED_FILE = Path(__file__).resolve().parent.parent / "sql" / "seed_postgres.sql"


def get_connection_pool() -> Any:
    """Retourne ou initialise le pool de connexions PostgreSQL."""
    global _connection_pool
    if psycopg2 is None or pool is None:
        raise RuntimeError("psycopg2 n'est pas installe dans cet environnement.")
    if _connection_pool is None or _connection_pool.closed:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )
    return _connection_pool


def close_connection_pool() -> None:
    """Ferme toutes les connexions du pool."""
    global _connection_pool
    if _connection_pool is not None and not _connection_pool.closed:
        _connection_pool.closeall()
        _connection_pool = None


@contextmanager
def get_db_cursor() -> Generator[Cursor, None, None]:
    """Gestionnaire de contexte pour obtenir un curseur avec rollback/commit automatique."""
    cp = get_connection_pool()
    conn = cp.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        cp.putconn(conn)


def hash_token(raw_token: str) -> str:
    """Calcule le hash SHA-256 d'un token d'authentification."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def init_db() -> None:
    """Execute le seed SQL idempotent pour les bases deja existantes."""
    try:
        seed_sql = SEED_FILE.read_text(encoding="utf-8")
        with get_db_cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id bigserial PRIMARY KEY,
                    user_id bigint NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                    token_hash varchar(64) NOT NULL UNIQUE,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    last_used_at timestamptz,
                    expires_at timestamptz NOT NULL,
                    is_active boolean NOT NULL DEFAULT true
                );
                CREATE INDEX IF NOT EXISTS admin_sessions_active_hash_idx
                    ON admin_sessions (token_hash) WHERE is_active = true;
                DELETE FROM api_tokens
                WHERE user_id IS NOT NULL
                   OR description LIKE 'Back-office login:%%';
                """
            )
            cur.execute(seed_sql)
        logger.info("Seed PostgreSQL execute avec succes depuis %s.", SEED_FILE)
    except OSError as exc:
        logger.error("Impossible de lire le seed PostgreSQL %s: %s", SEED_FILE, exc)
    except Exception as exc:
        logger.warning(
            "Impossible d'executer le seed PostgreSQL: %s", exc
        )


def verify_token_hash(token_hash: str) -> dict[str, object] | None:
    """Verifie si un hash de token existe et est actif dans PostgreSQL.

    Si valide, met a jour last_used_at et retourne les informations du token.
    """
    select_query = """
    SELECT
        t.id, t.token_hash, t.description, t.created_at,
        t.last_used_at, t.is_active, t.usage_count, u.role
    FROM api_tokens AS t
    LEFT JOIN app_users AS u ON u.id = t.user_id
    WHERE t.token_hash = %s AND t.is_active = TRUE;
    """
    update_query = """
    UPDATE api_tokens
    SET last_used_at = CURRENT_TIMESTAMP, usage_count = usage_count + 1
    WHERE id = %s;
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(select_query, (token_hash,))
            row = cur.fetchone()
            if row is None:
                return None

            token_id = row[0]
            cur.execute(update_query, (token_id,))
            return {
                "id": row[0],
                "token_hash": row[1],
                "description": row[2],
                "created_at": str(row[3]),
                "last_used_at": str(row[4]),
                "is_active": row[5],
                "usage_count": row[6],
                "role": row[7],
            }
    except Exception as exc:
        logger.error("Erreur lors de la verification du token en base: %s", exc)
        return None


def create_admin_session(
    raw_token: str,
    user_id: int,
    expires_at: str,
) -> None:
    query = """
    DELETE FROM admin_sessions
    WHERE expires_at <= CURRENT_TIMESTAMP OR is_active = FALSE;
    INSERT INTO admin_sessions (user_id, token_hash, expires_at)
    VALUES (%s, %s, %s);
    """
    with get_db_cursor() as cur:
        cur.execute(query, (user_id, hash_token(raw_token), expires_at))


def verify_admin_session(token_hash: str) -> dict[str, object] | None:
    query = """
    SELECT s.id, s.user_id, s.token_hash, u.username, u.role
    FROM admin_sessions AS s
    JOIN app_users AS u ON u.id = s.user_id
    WHERE s.token_hash = %s
      AND s.is_active = TRUE
      AND u.is_active = TRUE
      AND s.expires_at > CURRENT_TIMESTAMP;
    """
    update_query = """
    UPDATE admin_sessions
    SET last_used_at = CURRENT_TIMESTAMP
    WHERE token_hash = %s;
    """
    cleanup_query = """
    DELETE FROM admin_sessions
    WHERE expires_at <= CURRENT_TIMESTAMP OR is_active = FALSE;
    """
    with get_db_cursor() as cur:
        cur.execute(cleanup_query)
        cur.execute(query, (token_hash,))
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute(update_query, (token_hash,))
        return {
            "id": row[0],
            "user_id": row[1],
            "token_hash": row[2],
            "username": row[3],
            "role": row[4],
            "session": True,
        }


def revoke_admin_session(token_hash: str) -> None:
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE admin_sessions SET is_active = FALSE WHERE token_hash = %s",
            (token_hash,),
        )


def store_token(
    raw_token: str,
    description: str = "",
    user_id: int | None = None,
) -> dict[str, object]:
    """Hache un token brut et l'enregistre dans PostgreSQL.

    Retourne l'enregistrement cree (sans stocker le token en clair).
    """
    token_hash = hash_token(raw_token)
    insert_query = """
    INSERT INTO api_tokens (token_hash, description, user_id)
    VALUES (%s, %s, %s)
    RETURNING id, token_hash, description, created_at, is_active, user_id;
    """
    with get_db_cursor() as cur:
        cur.execute(insert_query, (token_hash, description, user_id))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Echec de l'insertion du token en base.")
        return {
            "id": row[0],
            "token_hash": row[1],
            "description": row[2],
            "created_at": str(row[3]),
            "is_active": row[4],
            "user_id": row[5],
        }


def generate_new_token(
    description: str = "",
    user_id: int | None = None,
) -> tuple[str, dict[str, object]]:
    """Genere un token aleatoire securise, calcule son hash et le stocke dans PostgreSQL."""
    raw_token = f"eco_{secrets.token_urlsafe(32)}"
    record = store_token(
        raw_token=raw_token,
        description=description,
        user_id=user_id,
    )
    return raw_token, record


if __name__ == "__main__":
    import sys

    token_desc = sys.argv[1] if len(sys.argv) > 1 else "default"
    print(f"Connexion a PostgreSQL via {DATABASE_URL}...")
    init_db()
    token, db_record = generate_new_token(description=token_desc)
    print("\nNouveau token genere avec succes !")
    print(f"Token brut (a utiliser avec 'Authorization: Bearer <token>') : {token}")
    print(f"Hash SHA-256 stocke en base : {db_record['token_hash']}")
    print(f"Description : {db_record['description']}")
