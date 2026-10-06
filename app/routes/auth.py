from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lib.db import generate_new_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    description: str = Field(default="", max_length=255)


class TokenResponse(BaseModel):
    token: str
    description: str
    created_at: datetime | str


@router.post("/token", response_model=TokenResponse)
@router.post("/tokens", response_model=TokenResponse, include_in_schema=False)
def generate_token(request: TokenRequest) -> TokenResponse:
    """Genere un token et ne le retourne qu'au moment de sa creation."""
    raw_token, record = generate_new_token(description=request.description)
    return TokenResponse(
        token=raw_token,
        description=request.description,
        created_at=record["created_at"],
    )
