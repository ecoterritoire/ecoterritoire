from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lib import influxdb


def test_queries_and_summary():
    record = SimpleNamespace(
        get_time=lambda: datetime(2025, 1, 1),
        get_value=lambda: 10,
        values={"Polluant": "NO", "code site": "A"},
    )
    list_record = SimpleNamespace(get_value=lambda: "NO")
    client = MagicMock()
    client.__enter__.return_value = client
    client.query_api.return_value.query.side_effect = [
        [SimpleNamespace(records=[record])],
        [SimpleNamespace(records=[record])],
        [SimpleNamespace(records=[list_record])],
    ]
    with patch("lib.influxdb._client", return_value=client):
        values = influxdb.query_timeline(
            date(2025, 1, 1), date(2025, 1, 1), 'N"O', "A\\B"
        )
        assert values[0]["value"] == 10
        assert influxdb.query_map(date(2025, 1, 1))
        with patch("lib.influxdb.query_map", return_value=[
            {"pollutant": "NO", "value": 10},
            {"pollutant": "NO", "value": 20},
            {"pollutant": "PM", "value": "bad"},
        ]):
            assert influxdb.query_summary(date(2025, 1, 1))[0]["average"] == 15.0
        assert influxdb.list_pollutants() == ["NO"]

    ping_client = MagicMock()
    ping_client.__enter__.return_value = ping_client
    ping_client.ping.return_value = True
    with patch("lib.influxdb._client", return_value=ping_client):
        assert influxdb.ping()
