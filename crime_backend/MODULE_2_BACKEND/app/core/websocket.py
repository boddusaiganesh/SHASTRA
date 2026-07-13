from fastapi import WebSocket
import json
import asyncio
from typing import Optional
from app.core.redis_connection import get_redis_client

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}

    def connect(self, websocket: WebSocket, user: dict):
        self.active_connections[websocket] = user

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast_local(self, data: dict, target_district: str | None = None):
        dead_connections = []
        for ws, user in self.active_connections.items():
            if target_district and target_district != "ALL" and user.get("role") == "DISTRICT_OFFICER" \
               and user.get("district_id") != target_district:
                continue
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead_connections.append(ws)
        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast(self, data: dict, target_district: str | None = None):
        """Publish to Redis so EVERY backend process (and the scheduler) fans out to its own local clients."""
        redis = get_redis_client()
        if redis:
            try:
                payload = json.dumps({"data": data, "target_district": target_district})
                await redis.publish("shastra:alerts", payload)
                return
            except Exception as e:
                import logging
                logging.getLogger("app.core.websocket").warning(f"Redis publish failed, falling back to local broadcast: {e}")
        await self.broadcast_local(data, target_district)

manager = ConnectionManager()

async def start_alert_subscriber():
    """Run once per worker process at startup to listen for Redis pub/sub alerts."""
    import logging
    logger = logging.getLogger("app.core.websocket")
    while True:
        try:
            redis = get_redis_client()
            if not redis:
                await asyncio.sleep(5)
                continue
            pubsub = redis.pubsub()
            await pubsub.subscribe("shastra:alerts")
            logger.info("Subscribed to Redis alerts pubsub channel 'shastra:alerts'")
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    await manager.broadcast_local(payload["data"], payload.get("target_district"))
                except Exception as e:
                    logger.error(f"Error handling pubsub message: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Alert subscriber connection lost ({e}), reconnecting in 5s...")
            await asyncio.sleep(5)
