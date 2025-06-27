from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"WebSocket disconnected. Total connections: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)

        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_job_update(
        self, job_id: UUID, event_type: str, data: Dict[str, Any]
    ):
        """Broadcast a job-specific update."""
        message = {
            "type": "job_update",
            "event": event_type,
            "job_id": str(job_id),
            "data": data,
            "timestamp": data.get("timestamp") or "now",
        }
        await self.broadcast(message)

    async def broadcast_system_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast a system-wide event."""
        message = {
            "type": "system_event",
            "event": event_type,
            "data": data,
            "timestamp": data.get("timestamp") or "now",
        }
        await self.broadcast(message)
