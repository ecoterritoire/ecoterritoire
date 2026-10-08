import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from app.routes.realtime import (
    _matches,
    _token_from_websocket,
    realtime_websocket,
    realtime_websocket_documentation,
)
from lib import realtime


def test_normalize_measurement_accepts_source_aliases():
    measurement = realtime.normalize_measurement(
        {
            "station_id": 42,
            "polluant": "NO2",
            "concentration": "12.5",
            "timestamp": "2026-10-08T12:00:00Z",
            "unite": "ug/m3",
        }
    )

    assert measurement == {
        "id": "42:NO2:2026-10-08T12:00:00Z:12.5",
        "time": "2026-10-08T12:00:00Z",
        "value": 12.5,
        "pollutant": "NO2",
        "code_site": "42",
        "unit": "ug/m3",
        "source": "https://data.sensor.community/airrohr/v1/filter/country=FR",
    }
    assert realtime.normalize_measurement({"pollutant": "NO2"}) is None
    assert realtime.normalize_measurement(
        {"code_site": "A", "pollutant": "NO2", "value": "bad", "time": "now"}
    ) is None


def test_payload_helpers_and_generic_source_errors():
    assert realtime._rows([{"id": 1}]) == [{"id": 1}]
    assert realtime._rows({"results": [{"id": 2}]}) == [{"id": 2}]
    assert realtime._rows({"data": "invalid"}) == []
    assert realtime._first({"a": None, "b": 2}, "a", "b") == 2

    with patch(
        "lib.realtime.settings",
        SimpleNamespace(realtime_source="generic", realtime_source_url="", realtime_source_token=""),
    ), pytest.raises(RuntimeError, match="REALTIME_SOURCE_URL"):
        realtime.fetch_measurements()


def test_fetch_measurements_reads_data_envelope():
    response = MagicMock()
    response.json.return_value = {
        "data": [
            {
                "code_site": "A",
                "pollutant": "PM10",
                "value": 8,
                "time": "2026-10-08T12:00:00Z",
            }
        ]
    }
    with patch(
        "lib.realtime.settings",
        SimpleNamespace(
            realtime_source="generic",
            realtime_source_url="https://source.test",
            realtime_source_token="",
        ),
    ), patch("lib.realtime.requests.get", return_value=response) as request:
        result = realtime.fetch_measurements()

    request.assert_called_once()
    response.raise_for_status.assert_called_once()
    assert result[0]["code_site"] == "A"


def test_fetch_open_meteo_measurements_without_account():
    response = MagicMock()
    response.json.return_value = {
        "current": {"time": "2026-10-08T12:00", "pm10": 10.4, "ozone": 39.0},
        "current_units": {"pm10": "ug/m3", "ozone": "ug/m3"},
    }
    config = SimpleNamespace(
        realtime_source="open_meteo",
        realtime_locations_json='[{"code_site":"A","latitude":48.8,"longitude":2.3}]',
    )
    with patch("lib.realtime.settings", config), patch(
        "lib.realtime.requests.get", return_value=response
    ):
        result = realtime.fetch_measurements()

    assert {item["pollutant"] for item in result} == {"PM10", "O3"}
    response.raise_for_status.assert_called_once()


def test_fetch_sensor_community_measurements():
    response = MagicMock()
    response.json.return_value = [
        {
            "sensor": {"id": 14770},
            "location": {"latitude": "45.222", "longitude": "5.688"},
            "timestamp": "2026-10-08 20:50:01",
            "sensordatavalues": [
                {"value_type": "P1", "value": "5.05"},
                {"value_type": "P2", "value": "1.73"},
                {"value_type": "temperature", "value": "20"},
            ],
        }
    ]
    config = SimpleNamespace(
        realtime_source="sensor_community",
        realtime_source_url="https://source.test",
    )
    with patch("lib.realtime.settings", config), patch(
        "lib.realtime.requests.get", return_value=response
    ):
        result = realtime.fetch_measurements()

    assert len(result) == 2
    assert result[0]["code_site"] == "sensor-14770"
    assert result[1]["pollutant"] == "PM2.5"
    assert result[1]["latitude"] == "45.222"


def test_open_meteo_rejects_invalid_locations():
    with patch(
        "lib.realtime.settings",
        SimpleNamespace(realtime_source="open_meteo", realtime_locations_json="invalid"),
    ), pytest.raises(RuntimeError, match="invalide"):
        realtime.fetch_measurements()

    with patch(
        "lib.realtime.settings",
        SimpleNamespace(realtime_source="open_meteo", realtime_locations_json="{}"),
    ), pytest.raises(RuntimeError, match="liste non vide"):
        realtime.fetch_measurements()


def test_publish_and_read_buffer():
    client = MagicMock()
    client.sismember.return_value = False
    pipeline = client.pipeline.return_value.__enter__.return_value
    config = SimpleNamespace(
        redis_url="redis://test",
        realtime_buffer_size=10,
        realtime_retention_seconds=60,
    )
    measurement = {"id": "1", "time": "now", "value": 1, "pollutant": "NO2", "code_site": "A"}
    with patch("lib.realtime.settings", config), patch(
        "lib.realtime._redis_client", return_value=client
    ):
        assert realtime.publish_measurements([measurement]) == 1
        client.lrange.return_value = ['{"id":"1"}']
        assert realtime.latest_measurements() == [{"id": "1"}]
    pipeline.execute.assert_called_once()


def test_publish_measurements_skips_seen_values():
    client = MagicMock()
    client.sismember.return_value = True
    pipeline = client.pipeline.return_value.__enter__.return_value
    with patch("lib.realtime._redis_client", return_value=client):
        assert realtime.publish_measurements(
            [{"id": "1", "time": "now", "value": 1, "pollutant": "NO2", "code_site": "A"}]
        ) == 0
    pipeline.execute.assert_not_called()


def test_websocket_filters_and_token_sources():
    websocket = SimpleNamespace(
        headers={"authorization": "Bearer abc"},
        query_params={},
    )
    assert _token_from_websocket(websocket) == "abc"
    assert _matches({"pollutant": "NO2", "code_site": "A"}, "NO2", "A")
    assert not _matches({"pollutant": "NO2", "code_site": "A"}, "PM10", None)
    assert realtime_websocket_documentation()["websocket_url"] == "/realtime/ws"


def test_websocket_rejects_missing_and_invalid_tokens():
    async def run_missing():
        websocket = SimpleNamespace(headers={}, query_params={}, close=AsyncMock())
        await realtime_websocket(websocket)
        websocket.close.assert_awaited_once()

    async def run_invalid():
        websocket = SimpleNamespace(
            headers={"authorization": "Bearer invalid"},
            query_params={},
            close=AsyncMock(),
        )
        with patch("app.routes.realtime.authenticate_token", side_effect=RuntimeError):
            await realtime_websocket(websocket)
        websocket.close.assert_awaited_once()

    asyncio.run(run_missing())
    asyncio.run(run_invalid())


def test_websocket_sends_throttled_heartbeat():
    class FakePubSub:
        def subscribe(self, _channel):
            return None

        def get_message(self, **_kwargs):
            return None

        def close(self):
            return None

    class FakeWebSocket:
        headers = {"authorization": "Bearer valid"}
        query_params = {}

        def __init__(self):
            self.messages = []

        async def accept(self):
            return None

        async def send_json(self, message):
            self.messages.append(message)
            if message["type"] == "heartbeat":
                raise WebSocketDisconnect()

    websocket = FakeWebSocket()
    client = MagicMock()
    client.pubsub.return_value = FakePubSub()
    with patch("app.routes.realtime.authenticate_token"), patch(
        "app.routes.realtime.realtime._redis_client", return_value=client
    ), patch(
        "app.routes.realtime.realtime.latest_measurements", return_value=[]
    ), patch("app.routes.realtime.HEARTBEAT_INTERVAL_SECONDS", 0):
        asyncio.run(realtime_websocket(websocket))

    assert [message["type"] for message in websocket.messages] == [
        "snapshot",
        "heartbeat",
    ]