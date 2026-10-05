from fastapi import APIRouter, Depends

from app.security.auth import get_current_token
from lib import influxdb

router = APIRouter(
    prefix="/pollutants",
    tags=["pollutants"],
    dependencies=[Depends(get_current_token)],
)


@router.get("")
def list_pollutants() -> dict[str, object]:
    return {"data": influxdb.list_pollutants()}
