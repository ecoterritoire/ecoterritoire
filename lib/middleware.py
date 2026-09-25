import logging
from collections.abc import Set
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from lib.db import hash_token, verify_token_hash

logger = logging.getLogger(__name__)

# Routes exemptees de verification d'authentification par defaut
DEFAULT_EXEMPT_PATHS: set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/auth/token",
    "/auth/tokens",
}


class AuthTokenMiddleware(BaseHTTPMiddleware):
    """Middleware FastAPI pour intercepter toutes les requetes de l'API.

    Valide le header 'Authorization: Bearer <token>', hache le token en SHA-256
    et verifie son existence et son statut actif dans PostgreSQL.
    """

    def __init__(
        self,
        app: Any,
        exempt_paths: Set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.exempt_paths = (
            set(exempt_paths) if exempt_paths is not None else DEFAULT_EXEMPT_PATHS
        )

    def is_exempt_path(self, path: str) -> bool:
        """Verifie si le chemin de la requete doit etre exempte d'authentification."""
        if path in self.exempt_paths:
            return True
        # Permet d'exempter les sous-chemins comme /docs/oauth2-redirect, etc.
        return any(path.startswith(f"{exempt}/") for exempt in self.exempt_paths)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # 1. Ne pas bloquer les routes de documentation, healthcheck ou creation de token initiale
        if self.is_exempt_path(path):
            return await call_next(request)

        # 2. Laisser passer les requetes OPTIONS (preflight CORS)
        if request.method == "OPTIONS":
            return await call_next(request)

        # 3. Recuperer le header Authorization
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4. Verifier le format Bearer <token>
        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid Authorization header format. Expected 'Bearer <token>'"
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        raw_token = parts[1]

        # 5. Hacher le token recu avec SHA-256
        token_hash = hash_token(raw_token)

        # 6. Verifier la validite du hash dans PostgreSQL
        token_data = verify_token_hash(token_hash)
        if not token_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or inactive authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 7. Attacher les donnees d'authentification au state de la requete
        request.state.auth_token = token_data

        return await call_next(request)
