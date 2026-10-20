import asyncio
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, auction_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.connections[auction_id].add(websocket)

    async def disconnect(self, auction_id: int, websocket: WebSocket):
        async with self.lock:
            self.connections[auction_id].discard(websocket)
            if not self.connections[auction_id]:
                self.connections.pop(auction_id, None)

    async def broadcast(self, auction_id: int, message: dict):
        async with self.lock:
            sockets = list(self.connections.get(auction_id, set()))
        dead = []
        for socket in sockets:
            try:
                await socket.send_json(message)
            except Exception:
                dead.append(socket)
        for socket in dead:
            await self.disconnect(auction_id, socket)

manager = ConnectionManager()
