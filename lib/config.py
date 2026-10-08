import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5433/ecoterritoire",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    auth_cache_ttl_seconds: int = int(os.getenv("AUTH_CACHE_TTL_SECONDS", "60"))
    admin_session_ttl_seconds: int = int(
        os.getenv("ADMIN_SESSION_TTL_SECONDS", "28800")
    )
    influxdb_url: str = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    influxdb_token: str = os.getenv("INFLUXDB_TOKEN", "ecoterritoire-dev-token")
    influxdb_org: str = os.getenv("INFLUXDB_ORG", "ecoterritoire")
    influxdb_bucket: str = os.getenv("INFLUXDB_BUCKET", "qualite-air")
    influxdb_measurement: str = os.getenv(
        "INFLUXDB_MEASUREMENT",
        "pollution_air",
    )
    realtime_source: str = os.getenv("REALTIME_SOURCE", "sensor_community")
    realtime_source_url: str = os.getenv(
        "REALTIME_SOURCE_URL",
        "https://data.sensor.community/airrohr/v1/filter/country=FR",
    )
    realtime_source_token: str = os.getenv("REALTIME_SOURCE_TOKEN", "")
    realtime_locations_json: str = os.getenv(
        "REALTIME_LOCATIONS_JSON",
        '[{"code_site":"paris","latitude":48.8566,"longitude":2.3522}]',
    )
    realtime_poll_interval_seconds: int = int(
        os.getenv("REALTIME_POLL_INTERVAL_SECONDS", "60")
    )
    realtime_retention_seconds: int = int(
        os.getenv("REALTIME_RETENTION_SECONDS", "900")
    )
    realtime_buffer_size: int = int(os.getenv("REALTIME_BUFFER_SIZE", "500"))


settings = Settings()
