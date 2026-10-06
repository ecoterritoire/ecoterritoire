from fastapi import APIRouter, Depends

from app.security.auth import get_current_token
from lib import postgres

router = APIRouter(
    prefix="/stations",
    tags=["stations"],
    dependencies=[Depends(get_current_token)],
)


@router.get("")
def list_stations(
    code_site: str | None = None,
    code_dpt: str | None = None,
) -> dict[str, object]:
    return {
        "data": postgres.list_stations(code_site=code_site, code_dpt=code_dpt),
    }
