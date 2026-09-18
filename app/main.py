from fastapi import FastAPI


app = FastAPI(title="Ecoterritoire API")


# Exemples de mesures, en attendant la connexion a InfluxDB.
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


@app.get("/measurements")
def list_measurements(
    polluant: str | None = None,
    zone: str | None = None,
    type_mesure: str | None = None,
    code_site: str | None = None,
    site: str | None = None,
) -> dict[str, object]:
    """Retourne les mesures avec des filtres correspondant aux tags InfluxDB."""
    filters = {
        "polluant": polluant,
        "zone": zone,
        "type_mesure": type_mesure,
        "code_site": code_site,
        "site": site,
    }
    results = [
        measurement
        for measurement in MEASUREMENTS
        if all(
            value is None or measurement[tag].lower() == value.lower()
            for tag, value in filters.items()
        )
    ]
    return {"count": len(results), "data": results}


@app.get("/measurements/{measurement_id}")
def get_measurement(measurement_id: int) -> dict[str, object]:
    """Retourne une mesure par son identifiant d'exemple."""
    for measurement in MEASUREMENTS:
        if measurement["id"] == measurement_id:
            return measurement
    return {"error": "Measurement not found"}