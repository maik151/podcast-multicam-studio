"""
Controlador WebSocket de Señalización WebRTC (Presentation Layer).
"""

from aiohttp import web
from core.application import SignalingHub

class SignalingController:
    def __init__(self, signaling_hub: SignalingHub):
        self.hub = signaling_hub

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        return await self.hub.handle_connection(request)
