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

_QR_SVG_CACHE = {}

def _render_qr_svg(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
        image_factory=qrcode.image.svg.SvgPathImage
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()

class NetworkController:
    def __init__(self, port: int):
        self.port = port
        self._warmup_qr_cache()

    def _warmup_qr_cache(self):
        """Pre-genera en memoria todos los códigos QR al iniciar el servidor (0ms response)."""
        try:
            primary_ip, _ = detect_primary_ip()
            urls_to_cache = []
            for cam_id in (1, 2, 3):
                urls_to_cache.extend([
                    f"http://localhost:8080/cam/{cam_id}",
                    f"https://localhost:8443/cam/{cam_id}",
                    f"https://127.0.0.1:8443/cam/{cam_id}",
                    f"http://127.0.0.1:8080/cam/{cam_id}",
                    f"https://{primary_ip}:{self.port}/cam/{cam_id}",
                    f"http://{primary_ip}:8080/cam/{cam_id}",
                ])
            for u in urls_to_cache:
                if u not in _QR_SVG_CACHE:
                    _QR_SVG_CACHE[u] = _render_qr_svg(u)
        except Exception:
            pass

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
            target_url = request.query.get("url") or request.query.get("data")
            if not target_url:
                primary_ip, _ = detect_primary_ip()
                target_url = f"https://{primary_ip}:{self.port}/cam/1"

            if target_url in _QR_SVG_CACHE:
                return web.Response(
                    body=_QR_SVG_CACHE[target_url],
                    content_type="image/svg+xml",
                    headers={
                        "Cache-Control": "public, max-age=86400, immutable",
                        "Access-Control-Allow-Origin": "*"
                    }
                )

            svg_bytes = _render_qr_svg(target_url)
            _QR_SVG_CACHE[target_url] = svg_bytes

            return web.Response(
                body=svg_bytes,
                content_type="image/svg+xml",
                headers={
                    "Cache-Control": "public, max-age=86400, immutable",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return web.Response(status=500, text=f"Error generando QR: {e}")

    async def handle_ping(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "app": "Podcast Multicam Studio Clean Core"})
