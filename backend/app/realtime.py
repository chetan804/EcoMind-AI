from collections import defaultdict
from typing import DefaultDict

from fastapi import WebSocket


class EventManager:
    def __init__(self) -> None:
        self.connections: DefaultDict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self.connections[user_id].discard(websocket)
        if not self.connections[user_id]:
            del self.connections[user_id]

    async def send_to_user(self, user_id: int, event: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for websocket in self.connections.get(user_id, set()):
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(user_id, websocket)


manager = EventManager()
