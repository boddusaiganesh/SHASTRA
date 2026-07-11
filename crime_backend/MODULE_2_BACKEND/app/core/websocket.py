from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}

    def connect(self, websocket: WebSocket, user: dict):
        self.active_connections[websocket] = user

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, data: dict, target_district: str | None = None):
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

manager = ConnectionManager()
