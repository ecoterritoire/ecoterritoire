from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.db import hash_token, verify_token_hash

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Saisissez uniquement votre token Bearer.",
    auto_error=False,
)


def authenticate_token(raw_token: str) -> dict[str, object]:
    token_data = verify_token_hash(hash_token(raw_token))
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
