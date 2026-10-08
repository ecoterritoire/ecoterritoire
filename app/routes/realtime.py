import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.security.auth import authenticate_token
from lib import realtime

router = APIRouter(prefix="/realtime", tags=["realtime"])
logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 30


@router.get(
    "/ws",
    summary="WebSocket temps réel",
    description=(
        "Documentation du canal WebSocket /realtime/ws. "
        "Connectez-vous avec un token Bearer ou le paramètre `token`, "
        "puis recevez les messages `snapshot`, `measurement` et `heartbeat`."
    ),
)
def realtime_websocket_documentation() -> dict[str, object]:
    return {
        "websocket_url": "/realtime/ws",
        "authentication": "Bearer token or ?token=<token>",
        "filters": ["pollutant", "code_site"],
        "messages": ["snapshot", "measurement", "heartbeat"],
    }


def _matches(measurement: dict[str, object], pollutant: str | None, code_site: str | None) -> bool:
    return (
        (pollutant is None or measurement.get("pollutant") == pollutant)
        and (code_site is None or measurement.get("code_site") == code_site)
    )


def _token_from_websocket(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return websocket.query_params.get("token")


@router.websocket("/ws")
async def realtime_websocket(
    websocket: WebSocket,
    pollutant: str | None = None,
    code_site: str | None = None,
) -> None:
    token = _token_from_websocket(websocket)
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    try:
        authenticate_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "type": "snapshot",
            "data": [
                measurement
                for measurement in await asyncio.to_thread(realtime.latest_measurements)
                if _matches(measurement, pollutant, code_site)
            ],
        }
    )
    client = realtime._redis_client()
    pubsub = client.pubsub()
    pubsub.subscribe(realtime.REALTIME_CHANNEL)
    last_heartbeat = time.monotonic()
    try:
        while True:
            message = await asyncio.to_thread(
                pubsub.get_message,
                ignore_subscribe_messages=True,
                timeout=1,
            )
            if message and message.get("data"):
                measurement = json.loads(message["data"])
                if _matches(measurement, pollutant, code_site):
                    await websocket.send_json({"type": "measurement", "data": measurement})
            elif time.monotonic() - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                await websocket.send_json({"type": "heartbeat"})
                last_heartbeat = time.monotonic()
    except WebSocketDisconnect:
        logger.debug("Client WebSocket temps reel deconnecte")
    finally:
        pubsub.close()
        client.close()