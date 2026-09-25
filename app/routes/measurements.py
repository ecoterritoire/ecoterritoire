from fastapi import APIRouter, Depends, Query

from app.data.measurements import (
    InMemoryMeasurementRepository,
    MeasurementFilters,
    MeasurementRepository,
)
from app.data.sample_measurements import MEASUREMENTS
from app.security import TokenSecurity


router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
    dependencies=[Depends(TokenSecurity.verifyToken)],
)


measurement_repository: MeasurementRepository = InMemoryMeasurementRepository(
    MEASUREMENTS
)


@router.get("")
def list_measurements(
    polluant: str | None = None,
    zone: str | None = None,
    type_mesure: str | None = None,
    code_site: str | None = None,
    site: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    """Retourne une page de mesures filtree par les tags InfluxDB."""
    start = (page - 1) * limit
    results = measurement_repository.find_page(
        filters=MeasurementFilters(
            polluant=polluant,
            zone=zone,
            type_mesure=type_mesure,
            code_site=code_site,
            site=site,
        ),
        offset=start,
        limit=limit,
    )

    return {
        "page": page,
        "limit": limit,
        "data": results,
    }


@router.get("/{measurement_id}")
def get_measurement(measurement_id: int) -> dict[str, object]:
    """Retourne une mesure par son identifiant d'exemple."""
    measurement = measurement_repository.find_by_id(measurement_id)
    if measurement is not None:
        return measurement
    return {"error": "Measurement not found"}
