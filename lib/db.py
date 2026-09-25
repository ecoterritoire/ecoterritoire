import hashlib
import logging
import os
import secrets
from collections.abc import Generator
from contextlib import contextmanager

from typing import Any

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extensions import cursor as Cursor
except ImportError:
    psycopg2 = None  # type: ignore
    pool = None  # type: ignore
    Cursor = Any  # type: ignore

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ecoterritoire:ecoterritoire@localhost:5432/ecoterritoire",
)

_connection_pool: pool.ThreadedConnectionPool | None = None


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
    """Initialise les tables necessaires dans PostgreSQL (table api_tokens)."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS api_tokens (
        id SERIAL PRIMARY KEY,
        token_hash VARCHAR(64) UNIQUE NOT NULL,
        description VARCHAR(255) DEFAULT '',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        last_used_at TIMESTAMP WITH TIME ZONE,
        is_active BOOLEAN DEFAULT TRUE
    );
    CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens (token_hash);
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(create_table_query)
        logger.info("Table api_tokens initialisee avec succes dans PostgreSQL.")
    except Exception as exc:
        logger.warning(
            "Impossible d'initialiser la base de donnees PostgreSQL: %s", exc
        )


def verify_token_hash(token_hash: str) -> dict[str, object] | None:
    """Verifie si un hash de token existe et est actif dans PostgreSQL.

    Si valide, met a jour last_used_at et retourne les informations du token.
    """
    select_query = """
    SELECT id, token_hash, description, created_at, last_used_at, is_active
    FROM api_tokens
    WHERE token_hash = %s AND is_active = TRUE;
    """
    update_query = """
    UPDATE api_tokens
    SET last_used_at = CURRENT_TIMESTAMP
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
            }
    except Exception as exc:
        logger.error("Erreur lors de la verification du token en base: %s", exc)
        return None


def store_token(raw_token: str, description: str = "") -> dict[str, object]:
    """Hache un token brut et l'enregistre dans PostgreSQL.

    Retourne l'enregistrement cree (sans stocker le token en clair).
    """
    token_hash = hash_token(raw_token)
    insert_query = """
    INSERT INTO api_tokens (token_hash, description)
    VALUES (%s, %s)
    RETURNING id, token_hash, description, created_at, is_active;
    """
    with get_db_cursor() as cur:
        cur.execute(insert_query, (token_hash, description))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Echec de l'insertion du token en base.")
        return {
            "id": row[0],
            "token_hash": row[1],
            "description": row[2],
            "created_at": str(row[3]),
            "is_active": row[4],
        }


def generate_new_token(description: str = "") -> tuple[str, dict[str, object]]:
    """Genere un token aleatoire securise, calcule son hash et le stocke dans PostgreSQL."""
    raw_token = f"eco_{secrets.token_urlsafe(32)}"
    record = store_token(raw_token=raw_token, description=description)
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
