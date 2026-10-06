from datetime import date
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query

from app.security.auth import get_current_token
from lib import influxdb, postgres

router = APIRouter(
    prefix="/pollution",
    tags=["pollution"],
    dependencies=[Depends(get_current_token)],
)


@router.get("/summary")
def pollution_summary(
    day: date = Query(default=date(2025, 1, 2)),
    pollutant: str | None = None,
) -> dict[str, object]:
    return {"date": day.isoformat(), "data": influxdb.query_summary(day, pollutant)}


@router.get("/map")
def pollution_map(
    day: date = Query(default=date(2025, 1, 1)),
    pollutant: str | None = None,
) -> dict[str, object]:
    values = influxdb.query_map(day, pollutant=pollutant)
    values_by_station: dict[str, list[dict[str, object]]] = {}
    for value in values:
        code_site = value.get("code_site")
        if isinstance(code_site, str):
            values_by_station.setdefault(code_site, []).append(value)

    pollutant_ranges: dict[str, tuple[float, float]] = {}
    if pollutant is None:
        values_by_pollutant: dict[str, list[float]] = {}
        for value in values:
            name = value.get("pollutant")
            numeric_value = value.get("value")
            if isinstance(name, str) and isinstance(numeric_value, (int, float)):
                values_by_pollutant.setdefault(name, []).append(float(numeric_value))
        pollutant_ranges = {
            name: (min(measurements), max(measurements))
            for name, measurements in values_by_pollutant.items()
        }

    data: list[dict[str, object]] = []
    for station in postgres.list_stations():
        station_values = values_by_station.get(station["code_site"], [])
        if pollutant and station_values:
            data.append({**station, **station_values[0]})
            continue

        scores: list[float] = []
        for value in station_values:
            name = value.get("pollutant")
            numeric_value = value.get("value")
            bounds = pollutant_ranges.get(name) if isinstance(name, str) else None
            if bounds and isinstance(numeric_value, (int, float)):
                minimum, maximum = bounds
                scores.append(
                    50.0
                    if maximum == minimum
                    else (float(numeric_value) - minimum) / (maximum - minimum) * 100
                )
        pollutant_names = [
            cast(str, value["pollutant"])
            for value in station_values
            if isinstance(value.get("pollutant"), str)
        ]
        data.append(
            {
                **station,
                "measurement_count": len(station_values),
                "pollutants": sorted(pollutant_names),
                "map_index": round(sum(scores) / len(scores), 1) if scores else None,
            }
        )

    return {"date": day.isoformat(), "data": data}


@router.get("/timeline")
def pollution_timeline(
    start: date = Query(default=date(2025, 1, 1)),
    stop: date = Query(default=date(2025, 12, 31)),
    pollutant: str | None = None,
    code_site: str | None = None,
) -> dict[str, object]:
    if stop < start:
        raise HTTPException(
            status_code=422,
            detail="stop must be greater than or equal to start",
        )

    return {
        "start": start.isoformat(),
        "stop": stop.isoformat(),
        "data": influxdb.query_timeline(
            start,
            stop,
            pollutant=pollutant,
            code_site=code_site,
        ),
    }
