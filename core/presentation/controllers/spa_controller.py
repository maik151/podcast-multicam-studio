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
        """Registra automáticamente todos los assets compilados por Angular en la raíz."""
        if os.path.exists(self.angular_dist_dir):
            for fname in os.listdir(self.angular_dist_dir):
                fpath = os.path.join(self.angular_dist_dir, fname)
                if os.path.isfile(fpath) and fname != "index.html":
                    app.router.add_get(
                        f"/{fname}",
                        (lambda p: lambda r: web.FileResponse(p, headers={"Cache-Control": "no-cache"}))(fpath)
                    )
