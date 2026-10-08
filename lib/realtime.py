import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests

from lib.config import settings

try:
    import redis
except ImportError:  # pragma: no cover - dependency is installed in production
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

REALTIME_CHANNEL = "ecoterritoire:realtime:measurements"
REALTIME_BUFFER_KEY = "ecoterritoire:realtime:buffer"
REALTIME_SEEN_KEY = "ecoterritoire:realtime:seen"
OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SENSOR_COMMUNITY_URL = "https://data.sensor.community/airrohr/v1/filter/country=FR"
OPEN_METEO_FIELDS = {
    "pm10": "PM10",
    "pm2_5": "PM2.5",
    "nitrogen_dioxide": "NO2",
    "ozone": "O3",
    "sulphur_dioxide": "SO2",
    "carbon_monoxide": "CO",
}


def _redis_client():
    if redis is None:
        raise RuntimeError("redis-py n'est pas installe dans cet environnement.")
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = payload.get("data", payload.get("results", payload.get("records", [])))
    else:
        values = []
    return [value for value in values if isinstance(value, dict)]


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return None


def normalize_measurement(row: dict[str, Any]) -> dict[str, Any] | None:
    code_site = _first(row, "code_site", "code site", "station", "station_id")
    pollutant = _first(row, "pollutant", "polluant", "Polluant", "pollutant_code")
    value = _first(row, "value", "valeur", "concentration", "measurement")
    measured_at = _first(row, "time", "timestamp", "date", "date_debut", "datetime")
    if code_site is None or pollutant is None or value is None or measured_at is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    timestamp = str(measured_at)
    identity = _first(row, "id", "measurement_id")
    if identity is None:
        identity = f"{code_site}:{pollutant}:{timestamp}:{numeric_value}"
    return {
        "id": str(identity),
        "time": timestamp,
        "value": numeric_value,
        "pollutant": str(pollutant),
        "code_site": str(code_site),
        "unit": _first(row, "unit", "unite", "unit_of_measurement"),
        "source": settings.realtime_source_url,
    }


def fetch_measurements() -> list[dict[str, Any]]:
    if settings.realtime_source == "open_meteo":
        return fetch_open_meteo_measurements()
    if settings.realtime_source == "sensor_community":
        return fetch_sensor_community_measurements()
    if not settings.realtime_source_url:
        raise RuntimeError("REALTIME_SOURCE_URL n'est pas configuree.")
    headers = {"Accept": "application/json"}
    if settings.realtime_source_token:
        headers["Authorization"] = f"Bearer {settings.realtime_source_token}"
    response = requests.get(
        settings.realtime_source_url,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return [
        measurement
        for row in _rows(response.json())
        if (measurement := normalize_measurement(row)) is not None
    ]


def fetch_sensor_community_measurements() -> list[dict[str, Any]]:
    response = requests.get(
        settings.realtime_source_url or SENSOR_COMMUNITY_URL,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    measurements: list[dict[str, Any]] = []
    for record in payload:
        if not isinstance(record, dict):
            continue
        sensor = record.get("sensor")
        location = record.get("location")
        values = record.get("sensordatavalues")
        if not isinstance(sensor, dict) or not isinstance(location, dict):
            continue
        if not isinstance(values, list):
            continue
        sensor_id = sensor.get("id")
        timestamp = record.get("timestamp")
        if sensor_id is None or timestamp is None:
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            pollutant = {"P1": "PM10", "P2": "PM2.5"}.get(item.get("value_type"))
            if pollutant is None:
                continue
            try:
                value = float(item["value"])
            except (KeyError, TypeError, ValueError):
                continue
            measurements.append(
                {
                    "id": f"sensor-community:{sensor_id}:{pollutant}:{timestamp}",
                    "time": str(timestamp),
                    "value": value,
                    "pollutant": pollutant,
                    "code_site": f"sensor-{sensor_id}",
                    "unit": "ug/m3",
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "source": settings.realtime_source_url or SENSOR_COMMUNITY_URL,
                }
            )
    return measurements


def fetch_open_meteo_measurements() -> list[dict[str, Any]]:
    try:
        locations = json.loads(settings.realtime_locations_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("REALTIME_LOCATIONS_JSON est invalide.") from exc
    if not isinstance(locations, list) or not locations:
        raise RuntimeError("REALTIME_LOCATIONS_JSON doit contenir une liste non vide.")

    measurements: list[dict[str, Any]] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        code_site = location.get("code_site")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if code_site is None or latitude is None or longitude is None:
            continue
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": ",".join(OPEN_METEO_FIELDS),
                "timezone": "UTC",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current", {})
        if not isinstance(current, dict):
            continue
        measured_at = current.get("time")
        if measured_at is None:
            continue
        for field, pollutant in OPEN_METEO_FIELDS.items():
            value = current.get(field)
            if value is None:
                continue
            measurements.append(
                {
                    "id": f"open-meteo:{code_site}:{pollutant}:{measured_at}",
                    "time": str(measured_at),
                    "value": float(value),
                    "pollutant": pollutant,
                    "code_site": str(code_site),
                    "unit": payload.get("current_units", {}).get(field, "ug/m3"),
                    "source": OPEN_METEO_URL,
                }
            )
    return measurements


def _ensure_time(measurement: dict[str, Any]) -> dict[str, Any]:
    if measurement.get("time"):
        return measurement
    return {**measurement, "time": datetime.now(timezone.utc).isoformat()}


def publish_measurements(measurements: list[dict[str, Any]]) -> int:
    if not measurements:
        return 0
    client = _redis_client()
    published = 0
    try:
        with client.pipeline() as pipeline:
            for measurement in measurements:
                measurement = _ensure_time(measurement)
                identity = measurement_id(measurement)
                if client.sismember(REALTIME_SEEN_KEY, identity):
                    continue
                encoded = json.dumps(measurement, ensure_ascii=True)
                pipeline.sadd(REALTIME_SEEN_KEY, identity)
                pipeline.lpush(REALTIME_BUFFER_KEY, encoded)
                pipeline.publish(REALTIME_CHANNEL, encoded)
                published += 1
            if published:
                pipeline.ltrim(REALTIME_BUFFER_KEY, 0, settings.realtime_buffer_size - 1)
                pipeline.expire(REALTIME_BUFFER_KEY, settings.realtime_retention_seconds)
                pipeline.expire(REALTIME_SEEN_KEY, settings.realtime_retention_seconds)
                pipeline.execute()
    finally:
        client.close()
    return published


def latest_measurements(limit: int = 100) -> list[dict[str, Any]]:
    client = _redis_client()
    try:
        values = client.lrange(REALTIME_BUFFER_KEY, 0, max(limit, 1) - 1)
    finally:
        client.close()
    return [json.loads(value) for value in values]


def measurement_id(measurement: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(measurement, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()