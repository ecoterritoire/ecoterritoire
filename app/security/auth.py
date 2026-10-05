import json
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.config import settings
from lib.db import hash_token, verify_admin_session, verify_token_hash

try:
    import redis
except ImportError:  # pragma: no cover - dependency is installed in production
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
_redis_client = None

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Saisissez uniquement votre token Bearer.",
    auto_error=False,
)


def _get_redis_client():
    global _redis_client
    if redis is None:
        return None
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_client


def _cache_key(token_hash: str) -> str:
    return f"ecoterritoire:auth:{token_hash}"


def _usage_key(token_id: object) -> str:
    return f"ecoterritoire:auth-usage:{token_id}"


def _record_cached_usage(token_id: object) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.incr(_usage_key(token_id))
    except Exception as exc:
        logger.warning("Impossible d'enregistrer l'utilisation Redis: %s", exc)


def _get_cached_token(token_hash: str) -> dict[str, object] | None:
    client = _get_redis_client()
    if client is None:
        return None
    try:
        cached = client.get(_cache_key(token_hash))
        if cached is None:
            return None
        value = json.loads(cached)
        return value if isinstance(value, dict) else None
    except Exception as exc:
        logger.warning("Cache Redis indisponible pendant la lecture du token: %s", exc)
        return None


def _cache_token(token_hash: str, token_data: dict[str, object]) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(
            _cache_key(token_hash),
            settings.auth_cache_ttl_seconds,
            json.dumps(token_data),
        )
    except Exception as exc:
        logger.warning("Cache Redis indisponible pendant l'ecriture du token: %s", exc)


def invalidate_token_cache(token_hash: str) -> None:
    """Supprime immédiatement un token du cache après révocation."""
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.delete(_cache_key(token_hash))
    except Exception as exc:
        logger.warning("Impossible d'invalider le cache Redis du token: %s", exc)


def authenticate_token(raw_token: str) -> dict[str, object]:
    token_hash = hash_token(raw_token)
    token_data = _get_cached_token(token_hash)
    if token_data is None:
        token_data = verify_token_hash(token_hash)
        if token_data is not None:
            _cache_token(token_hash, token_data)
    else:
        _record_cached_usage(token_data.get("id"))
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


def get_current_token(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> dict[str, object]:
    """Retourne le token authentifie et le rend disponible aux routes."""
    token_data = getattr(request.state, "auth_token", None)
    if isinstance(token_data, dict):
        return token_data

    if credentials is None:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authenticate_token(credentials.credentials)


def get_current_admin_session(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> dict[str, object]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = verify_admin_session(hash_token(credentials.credentials))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired administrator session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session
