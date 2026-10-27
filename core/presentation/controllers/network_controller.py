"""
Controlador HTTP de Red y Códigos QR (Presentation Layer).
"""

import io
from aiohttp import web
import qrcode
import qrcode.image.svg
from core.infrastructure.network import get_network_diagnostics, detect_primary_ip

class NetworkController:
    def __init__(self, port: int):
        self.port = port

    async def handle_diagnostics(self, request: web.Request) -> web.Response:
        diag = get_network_diagnostics(self.port)
        return web.json_response(diag)

    async def handle_qr(self, request: web.Request) -> web.Response:
        try:
            primary_ip, _ = detect_primary_ip()
            default_target = f"https://{primary_ip}:{self.port}/cam/1"
            target_url = request.query.get("url") or request.query.get("data") or default_target

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
                image_factory=qrcode.image.svg.SvgPathImage
            )
            qr.add_data(target_url)
            qr.make(fit=True)
            img = qr.make_image()

            buf = io.BytesIO()
            img.save(buf)
            return web.Response(
                body=buf.getvalue(),
                content_type="image/svg+xml",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return web.Response(status=500, text=f"Error generando QR: {e}")

    async def handle_ping(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "app": "Podcast Multicam Studio Clean Core"})
