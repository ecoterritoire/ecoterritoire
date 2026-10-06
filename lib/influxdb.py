from datetime import date, datetime, timedelta, timezone
from typing import Any

from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import WriteOptions

from lib.config import settings


def _client() -> InfluxDBClient:
    return InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
    )


def get_client() -> InfluxDBClient:
    return _client()


def get_write_api(client: InfluxDBClient):
    return client.write_api(
        write_options=WriteOptions(
            batch_size=5000,
            flush_interval=1000,
            jitter_interval=0,
            retry_interval=5000,
            max_retries=5,
        )
    )


def ping() -> bool:
    with _client() as client:
        return client.ping()


def _flux_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _range_filter(start: datetime, stop: datetime) -> str:
    return (
        f'|> range(start: time(v: "{start.isoformat()}"), '
        f'stop: time(v: "{stop.isoformat()}"))'
    )


def query_timeline(
    start: date,
    stop: date,
    pollutant: str | None = None,
    code_site: str | None = None,
) -> list[dict[str, Any]]:
    start_at = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    stop_at = datetime.combine(stop + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    filters = [
        f'r._measurement == "{_flux_string(settings.influxdb_measurement)}"',
        'r._field == "moyenne"',
    ]
    if pollutant:
        filters.append(f'r["Polluant"] == "{_flux_string(pollutant)}"')
    if code_site:
        filters.append(f'r["code site"] == "{_flux_string(code_site)}"')

    query = f'''
        from(bucket: "{_flux_string(settings.influxdb_bucket)}")
        {_range_filter(start_at, stop_at)}
        |> filter(fn: (r) => {' and '.join(filters)})
        |> keep(columns: ["_time", "_value", "Polluant", "code site"])
        |> sort(columns: ["_time"])
    '''

    with _client() as client:
        records = client.query_api().query(query=query, org=settings.influxdb_org)
        return [
            {
                "time": record.get_time().isoformat(),
                "value": record.get_value(),
                "pollutant": record.values.get("Polluant"),
                "code_site": record.values.get("code site"),
            }
            for table in records
            for record in table.records
        ]


def query_map(day: date, pollutant: str | None = None) -> list[dict[str, Any]]:
    return query_timeline(day, day, pollutant=pollutant)


def query_summary(day: date, pollutant: str | None = None) -> list[dict[str, Any]]:
    values = query_map(day, pollutant=pollutant)
    grouped: dict[str, list[float]] = {}
    for value in values:
        name = value.get("pollutant")
        numeric_value = value.get("value")
        if name and isinstance(numeric_value, (int, float)):
            grouped.setdefault(name, []).append(float(numeric_value))

    return [
        {
            "pollutant": name,
            "average": round(sum(measurements) / len(measurements), 3),
            "minimum": round(min(measurements), 3),
            "maximum": round(max(measurements), 3),
            "stations": len(measurements),
        }
        for name, measurements in sorted(grouped.items())
    ]


def list_pollutants() -> list[str]:
    query = f'''
        from(bucket: "{_flux_string(settings.influxdb_bucket)}")
        |> range(start: 1970-01-01T00:00:00Z)
        |> filter(fn: (r) => r._measurement == "{_flux_string(settings.influxdb_measurement)}")
        |> keep(columns: ["Polluant"])
        |> group()
        |> distinct(column: "Polluant")
        |> sort()
    '''

    with _client() as client:
        records = client.query_api().query(query=query, org=settings.influxdb_org)
        return sorted(
            {
                record.get_value()
                for table in records
                for record in table.records
                if record.get_value()
            }
        )
