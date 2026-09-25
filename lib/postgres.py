from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg2 import connect
from psycopg2.extras import execute_values
from psycopg2.extras import execute_values
from psycopg2.extensions import connection

from lib.config import settings


@contextmanager
def get_connection() -> Iterator[connection]:
    database = connect(settings.database_url)
    try:
        yield database
    finally:
        database.close()


def list_stations(
    code_site: str | None = None,
    code_dpt: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            code_site,
            nom_site,
            organisme,
            code_zas,
            zas,
            type_implantation,
            code_insee,
            code_dpt,
            latitude,
            longitude
        FROM stations
        WHERE (%s IS NULL OR code_site = %s)
          AND (%s IS NULL OR code_dpt = %s)
        ORDER BY nom_site, code_site
    """

    with get_connection() as database:
        with database.cursor() as cursor:
            cursor.execute(query, (code_site, code_site, code_dpt, code_dpt))
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def stations_by_code(codes: list[str]) -> dict[str, dict[str, Any]]:
    if not codes:
        return {}

    query = """
        SELECT
            code_site,
            nom_site,
            organisme,
            code_zas,
            zas,
            type_implantation,
            code_insee,
            code_dpt,
            latitude,
            longitude
        FROM stations
        WHERE code_site = ANY(%s)
    """

    with get_connection() as database:
        with database.cursor() as cursor:
            cursor.execute(query, (codes,))
            columns = [description[0] for description in cursor.description]
            return {
                row[0]: dict(zip(columns, row))
                for row in cursor.fetchall()
            }


def upsert_stations(stations: list[tuple[Any, ...]]) -> None:
    if not stations:
        return

    query = """
        INSERT INTO stations (
            code_site, nom_site, organisme, code_zas, zas, type_implantation
        ) VALUES %s
        ON CONFLICT (code_site) DO UPDATE SET
            nom_site = EXCLUDED.nom_site,
            organisme = EXCLUDED.organisme,
            code_zas = EXCLUDED.code_zas,
            zas = EXCLUDED.zas,
            type_implantation = EXCLUDED.type_implantation,
            updated_at = now()
    """

    with get_connection() as database:
        with database.cursor() as cursor:
            execute_values(cursor, query, stations)
        database.commit()


def update_station_coordinates(rows: list[tuple[str, float, float]]) -> int:
    if not rows:
        return 0

    query = """
        UPDATE stations AS local
        SET latitude = metadata.latitude,
            longitude = metadata.longitude,
            position = ST_SetSRID(
                ST_MakePoint(metadata.longitude, metadata.latitude), 4326
            ),
            updated_at = now()
        FROM (VALUES %s) AS metadata(code_site, latitude, longitude)
        WHERE local.code_site = metadata.code_site
    """

    with get_connection() as database:
        with database.cursor() as cursor:
            execute_values(cursor, query, rows, page_size=len(rows))
            updated = cursor.rowcount
        database.commit()
    return updated


def upsert_stations(stations: list[tuple[Any, ...]]) -> None:
    if not stations:
        return

    query = """
        INSERT INTO stations (
            code_site, nom_site, organisme, code_zas, zas, type_implantation
        ) VALUES %s
        ON CONFLICT (code_site) DO UPDATE SET
            nom_site = EXCLUDED.nom_site,
            organisme = EXCLUDED.organisme,
            code_zas = EXCLUDED.code_zas,
            zas = EXCLUDED.zas,
            type_implantation = EXCLUDED.type_implantation,
            updated_at = now()
    """

    with get_connection() as database:
        with database.cursor() as cursor:
            execute_values(cursor, query, stations)
        database.commit()
