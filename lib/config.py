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


settings = Settings()
