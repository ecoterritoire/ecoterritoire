from datetime import date

from fastapi import APIRouter, Depends, Query

from app.routes.pollution import pollution_timeline
from app.security.auth import get_current_token

router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
    dependencies=[Depends(get_current_token)],
)


@router.get("")
def list_measurements(
    pollutant: str | None = None,
    code_site: str | None = None,
    start: date = Query(default=date(2025, 1, 1)),
    stop: date = Query(default=date(2025, 12, 31)),
) -> dict[str, object]:
    return pollution_timeline(
        start=start,
        stop=stop,
        pollutant=pollutant,
        code_site=code_site,
    )
