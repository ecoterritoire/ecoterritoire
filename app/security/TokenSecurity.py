import secrets
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(
    scheme_name="BearerAuth",
    description="Saisissez uniquement votre token Bearer.",
)

class Token(BaseModel):
    name: str
    hash_token: str
    created_at: datetime

FAKE_USERS_DB = [
    Token(
        name="Alice",
        hash_token="1234",
        created_at=datetime(2026, 1, 1, 12, 0),
    ),
    Token(
        name="Bob",
        hash_token="1234",
        created_at=datetime(2026, 2, 15, 14, 30),
    ),
]

def verifyToken(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Token:
    token_string = credentials.credentials
    
    user_data = next(
        (user for user in FAKE_USERS_DB if user.hash_token == token_string),
        None,
    )
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou utilisateur introuvable",
        )
    
    return user_data


def generate_token(name: str) -> Token:
    token = Token(
        name=name,
        hash_token=secrets.token_urlsafe(32),
        created_at=datetime.now(),
    )
    FAKE_USERS_DB.append(token)
    return token