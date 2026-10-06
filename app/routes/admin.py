from pathlib import Path
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.security.auth import get_current_admin_session
from lib import admin as admin_db
from lib.config import settings
from lib.db import create_admin_session, generate_new_token, revoke_admin_session

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def admin_page(request: Request) -> Any:
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
    )


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    token: str
    username: str
    role: str


class ApiKeyCreateRequest(BaseModel):
    description: str = Field(default="", max_length=255)


class ApiKeyCreateResponse(BaseModel):
    token: str
    description: str


def require_admin(
    token: Annotated[dict[str, object], Depends(get_current_admin_session)],
) -> dict[str, object]:
    if token.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return token


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(request: AdminLoginRequest) -> AdminLoginResponse:
    user = admin_db.find_user(request.username)
    if user is None or not admin_db.verify_password(
        request.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials",
        )

    user_id = int(user["id"])
    token = f"eco_admin_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.admin_session_ttl_seconds
    )
    create_admin_session(token, user_id, expires_at.isoformat())
    return AdminLoginResponse(
        token=token,
        username=user["username"],
        role=user["role"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(
    token: Annotated[dict[str, object], Depends(get_current_admin_session)],
) -> None:
    revoke_admin_session(str(token["token_hash"]))


@router.get("/tokens")
def list_tokens(
    _: Annotated[dict[str, object], Depends(require_admin)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    active_only: bool = False,
) -> dict[str, Any]:
    return {
        "data": admin_db.list_api_tokens(limit, offset, active_only),
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
def stats(
    _: Annotated[dict[str, object], Depends(require_admin)],
) -> dict[str, int]:
    return admin_db.api_stats()


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
def create_api_key(
    request: ApiKeyCreateRequest,
    _: Annotated[dict[str, object], Depends(require_admin)],
) -> ApiKeyCreateResponse:
    raw_token, _ = generate_new_token(description=request.description.strip())
    return ApiKeyCreateResponse(
        token=raw_token,
        description=request.description.strip(),
    )
