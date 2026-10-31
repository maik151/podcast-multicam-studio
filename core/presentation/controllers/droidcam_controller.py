"""
Controlador de API para integración con DroidCam USB (Android e iOS).
Gestiona detección de dispositivos, enlace de puertos locales por cámara y proxy de stream de video.
"""

from aiohttp import web
import aiohttp
from core.network.droidcam_bridge import droidcam_bridge


class DroidCamController:
    """Controlador REST para gestión de flujos de cámara USB DroidCam."""

    def __init__(self):
        self.bridge = droidcam_bridge

    async def handle_devices(self, request: web.Request) -> web.Response:
        """Escanea y retorna todos los dispositivos Android e iOS conectados por cable USB."""
        data = self.bridge.scan_devices()
        return web.json_response(data)

    async def handle_status(self, request: web.Request) -> web.Response:
        """Retorna el estado de enlace actual de las 3 cámaras."""
        data = self.bridge.get_bindings_summary()
        return web.json_response(data)

    async def handle_bind(self, request: web.Request) -> web.Response:
        """Enlaza un teléfono (Android o iOS) a una cámara (1..3)."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "message": "JSON body inválido"}, status=400)

        cam_id = int(body.get("cam_id", 1))
        device_id = str(body.get("device_id", "")).strip()
        platform = str(body.get("platform", "android")).strip().lower()

        if not device_id:
            # Si no especifica device_id pero hay 1 dispositivo conectado de esa plataforma, enlazar automáticamente
            scan = self.bridge.scan_devices()
            devs = [d for d in scan.get("devices", []) if d.get("platform") == platform]
            if devs:
                device_id = str(devs[0].get("id") or devs[0].get("serial", ""))

        if not device_id:
            return web.json_response({"success": False, "message": "No se detectó ningún teléfono conectado para enlazar."}, status=400)

        res = self.bridge.bind_camera(cam_id, device_id, platform)
        status_code = 200 if res.get("success") else 400
        return web.json_response(res, status=status_code)

    async def handle_unbind(self, request: web.Request) -> web.Response:
        """Libera la asignación de puerto de una cámara."""
        try:
            body = await request.json()
            cam_id = int(body.get("cam_id", 1))
        except Exception:
            cam_id = 1

        res = self.bridge.unbind_camera(cam_id)
        return web.json_response(res)

    async def handle_feed(self, request: web.Request) -> web.StreamResponse:
        """
        Proxy HTTP de ultra-baja latencia para el stream de video de DroidCam.
        Evita advertencias de Mixed Content en navegadores HTTPS y permite consumo directo por <img> o <canvas>.
        """
        try:
            cam_id = int(request.match_info.get("cam_id", "1"))
        except ValueError:
            cam_id = 1

        binding = self.bridge.active_bindings.get(cam_id)
        port = binding["local_port"] if binding else self.bridge.camera_ports.get(cam_id, 4741)
        target_url = f"http://127.0.0.1:{port}/video"

        timeout = aiohttp.ClientTimeout(total=None, connect=1.5, sock_read=5.0)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(target_url) as resp:
                    if resp.status != 200:
                        return web.Response(
                            status=503,
                            text=f"El stream de DroidCam en puerto {port} no está emitiendo aún (HTTP {resp.status}). Abre la app en el teléfono.",
                            content_type="text/plain"
                        )

                    content_type = resp.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=--droidcam")
                    headers = {
                        "Content-Type": content_type,
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Access-Control-Allow-Origin": "*"
                    }
                    stream_resp = web.StreamResponse(status=200, headers=headers)
                    await stream_resp.prepare(request)

                    async for chunk in resp.content.iter_chunked(32768):
                        await stream_resp.write(chunk)

                    return stream_resp
        except Exception as exc:
            return web.Response(
                status=503,
                text=f"Esperando inicio de la app DroidCam en el teléfono (puerto {port}): {exc}",
                content_type="text/plain"
            )
