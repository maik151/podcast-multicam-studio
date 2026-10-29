"""
Controlador HTTP de Red y Códigos QR (Presentation Layer).
"""

import io
from aiohttp import web
import qrcode
import qrcode.image.svg
from core.infrastructure.network import (
    get_network_diagnostics,
    detect_primary_ip,
    get_full_connection_matrix,
    reverse_all_adb_devices,
    open_windows_hotspot_settings
)

class NetworkController:
    def __init__(self, port: int):
        self.port = port

    async def handle_diagnostics(self, request: web.Request) -> web.Response:
        diag = get_network_diagnostics(self.port)
        return web.json_response(diag)

    async def handle_connections(self, request: web.Request) -> web.Response:
        """Devuelve la matriz de conexiones completas (USB Hub ADB, Hotspot 5GHz, Tethering y LAN)."""
        matrix = get_full_connection_matrix(self.port)
        return web.json_response(matrix)

    async def handle_adb_reverse(self, request: web.Request) -> web.Response:
        """Invierte los puertos ADB (reverse tcp:8443) para todos los teléfonos Android conectados vía USB."""
        result = reverse_all_adb_devices(self.port)
        return web.json_response(result)

    async def handle_open_hotspot(self, request: web.Request) -> web.Response:
        """Abre la configuración del Hotspot Móvil de Windows."""
        success = open_windows_hotspot_settings()
        return web.json_response({"success": success})

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
