from datetime import date
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routes import pollution


def test_pollution_map():
    stations = [
        {"code_site": "A", "nom_site": "One"},
        {"code_site": "B", "nom_site": "Two"},
    ]
    values = [
        {"code_site": "A", "pollutant": "NO", "value": 10},
        {"code_site": "A", "pollutant": "PM", "value": 20},
        {"code_site": "B", "pollutant": "NO", "value": 10},
    ]
    with patch("app.routes.pollution.postgres.list_stations", return_value=stations), patch(
        "app.routes.pollution.influxdb.query_map", return_value=values
    ):
        result = pollution.pollution_map(date(2025, 1, 1))
        assert result["data"][0]["map_index"] == 50.0
        filtered = pollution.pollution_map(date(2025, 1, 1), "NO")
        assert filtered["data"][0]["value"] == 10


def test_pollution_timeline():
    with patch("app.routes.pollution.influxdb.query_timeline", return_value=[]):
        assert pollution.pollution_timeline(
            date(2025, 1, 1), date(2025, 1, 2)
        )["data"] == []
    with pytest.raises(HTTPException):
        pollution.pollution_timeline(date(2025, 1, 2), date(2025, 1, 1))
