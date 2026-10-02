import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://ecoterritoire:ecoterritoire@localhost:5433/ecoterritoire",
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
