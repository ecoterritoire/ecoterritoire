import os
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# Permet l'exécution directe depuis le dossier `script/`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib import postgres

load_dotenv()

METADATA_URL = os.getenv(
    "STATION_METADATA_URL",
    "https://www.data.gouv.fr/api/1/datasets/r/eb87c56c-dea9-4377-a1e7-03ada59d3043",
)
def download_stations() -> pd.DataFrame:
    response = requests.get(METADATA_URL, timeout=120)
    response.raise_for_status()
    stations = pd.read_excel(
        BytesIO(response.content),
        sheet_name="AirQualityStations",
        dtype={"NatlStationCode": str},
    )
    required = {"NatlStationCode", "Latitude", "Longitude"}
    missing = required - set(stations.columns)
    if missing:
        raise RuntimeError(f"Colonnes manquantes dans le référentiel: {sorted(missing)}")
    return stations


def normalize_rows(frame: pd.DataFrame) -> list[tuple[str, float, float]]:
    rows = frame[["NatlStationCode", "Latitude", "Longitude"]].copy()
    rows["NatlStationCode"] = rows["NatlStationCode"].astype("string").str.strip()
    rows["Latitude"] = pd.to_numeric(rows["Latitude"], errors="coerce")
    rows["Longitude"] = pd.to_numeric(rows["Longitude"], errors="coerce")
    rows = rows.dropna().drop_duplicates(subset=["NatlStationCode"])
    rows = rows[rows["NatlStationCode"].str.len() > 0]
    return list(rows.itertuples(index=False, name=None))


def update_stations(rows: list[tuple[str, float, float]]) -> int:
    return postgres.update_station_coordinates(rows)


def main() -> None:
    rows = normalize_rows(download_stations())
    updated = update_stations(rows)
    print(f"Coordonnees lues : {len(rows)}")
    print(f"Stations mises a jour : {updated}")
    print(f"Stations sans correspondance : {len(rows) - updated}")


if __name__ == "__main__":
    main()
