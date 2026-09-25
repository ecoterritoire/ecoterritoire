from fastapi import APIRouter
from pydantic import BaseModel

from app.security import TokenSecurity


router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    name: str


@router.post("/token", response_model=TokenSecurity.Token)
def generate_token(request: TokenRequest) -> TokenSecurity.Token:
    """Genere un token sans authentification prealable."""
    return TokenSecurity.generate_token(request.name)
