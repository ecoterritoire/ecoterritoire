from fastapi import FastAPI, Query

from app.data.measurements import (
    InMemoryMeasurementRepository,
    MeasurementFilters,
    MeasurementRepository,
)


app = FastAPI(title="Ecoterritoire API")


MEASUREMENTS = [
    {
        "id": 1,
        "time": "2025-01-01T00:01:50Z",
        "value": 1.3,
        "organisation": "AIR BREIZH",
        "polluant": "NO",
        "zone": "ZAG RENNES",
        "type_mesure": "minimum",
        "code_site": "FR19002",
        "site": "Rennes Laennec",
        "unite": "µg-m3",
    },
    {
        "id": 2,
        "time": "2025-01-01T00:01:50Z",
        "value": 2.929,
        "organisation": "AIR BREIZH",
        "polluant": "NO",
        "zone": "ZAG RENNES",
        "type_mesure": "moyenne",
        "code_site": "FR19002",
        "site": "Rennes Laennec",
        "unite": "µg-m3",
    },
    {
        "id": 3,
        "time": "2025-01-01T00:01:50Z",
        "value": 2.4,
        "organisation": "AIR BREIZH",
        "polluant": "NO",
        "zone": "ZAG RENNES",
        "type_mesure": "maximum",
        "code_site": "FR19007",
        "site": "Rennes Les Halles",
        "unite": "µg-m3",
    },
]


measurement_repository: MeasurementRepository = InMemoryMeasurementRepository(
    MEASUREMENTS
)


@app.get("/measurements")
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


@app.get("/measurements/{measurement_id}")
def get_measurement(measurement_id: int) -> dict[str, object]:
    """Retourne une mesure par son identifiant d'exemple."""
    measurement = measurement_repository.find_by_id(measurement_id)
    if measurement is not None:
        return measurement
    return {"error": "Measurement not found"}