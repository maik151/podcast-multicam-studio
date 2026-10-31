"""
Controlador SPA y entrega de clientes Frontend (Angular 19 / PWA Mobile).
"""

import os
from aiohttp import web

class SpaController:
    def __init__(self, angular_dist_dir: str, static_dir: str):
        self.angular_dist_dir = angular_dist_dir
        self.static_dir = static_dir

    async def handle_index(self, request: web.Request) -> web.StreamResponse:
        """Sirve la consola principal de dirección (Angular SPA o fallback legacy)."""
        user_agent = request.headers.get("User-Agent", "").lower()
        is_mobile = any(m in user_agent for m in ["iphone", "android", "ipad", "mobile"])
        if is_mobile:
            raise web.HTTPFound("/cam/1")

        angular_index = os.path.join(self.angular_dist_dir, "index.html")
        if os.path.exists(angular_index):
            return web.FileResponse(angular_index, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
        return web.FileResponse(os.path.join(self.static_dir, "director", "index.html"))

    async def handle_camera(self, request: web.Request) -> web.FileResponse:
        """Sirve la interfaz web PWA (Angular SPA o fallback legacy)."""
        angular_index = os.path.join(self.angular_dist_dir, "index.html")
        if os.path.exists(angular_index):
            return web.FileResponse(angular_index, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
        return web.FileResponse(os.path.join(self.static_dir, "mobile", "index.html"))

    def register_angular_dist_routes(self, app: web.Application) -> None:
        """Registra la entrega dinámica de todos los assets compilados por Angular sin necesidad de reiniciar el servidor."""
        async def handle_static_asset(request: web.Request) -> web.StreamResponse:
            fname = request.match_info.get("filename", "")
            # 1. Probar en angular_dist_dir
            p1 = os.path.join(self.angular_dist_dir, fname)
            if os.path.isfile(p1):
                return web.FileResponse(p1, headers={"Cache-Control": "no-cache"})
            # 2. Probar en static/director
            p2 = os.path.join(self.static_dir, "director", fname)
            if os.path.isfile(p2):
                return web.FileResponse(p2, headers={"Cache-Control": "no-cache"})
            # 3. Probar en static/
            p3 = os.path.join(self.static_dir, fname)
            if os.path.isfile(p3):
                return web.FileResponse(p3, headers={"Cache-Control": "no-cache"})
            return web.Response(status=404, text=f"Asset '{fname}' no encontrado")

        app.router.add_get(r"/{filename:.+\.(?:js|css|ico|svg|png|webmanifest|json|woff2|woff|ttf|map)}", handle_static_asset)
