from unittest.mock import MagicMock, patch

from lib import postgres
from tests.helpers import DatabaseContext


def test_station_operations():
    cursor = MagicMock()
    cursor.description = [(name,) for name in ("code_site", "nom_site")]
    cursor.fetchall.return_value = [("A", "Station")]
    database = DatabaseContext(cursor)

    with patch("lib.postgres.get_connection", return_value=database):
        assert postgres.list_stations()[0]["code_site"] == "A"
        assert postgres.stations_by_code(["A"])["A"]["nom_site"] == "Station"
        assert postgres.stations_by_code([]) == {}
        assert postgres.upsert_stations([]) is None
        assert postgres.update_station_coordinates([]) == 0

    cursor.rowcount = 1
    with patch("lib.postgres.get_connection", return_value=database), patch(
        "lib.postgres.execute_values"
    ):
        postgres.upsert_stations([("A", "Station")])
        assert postgres.update_station_coordinates([("A", 1.0, 2.0)]) == 1
        assert database.committed
