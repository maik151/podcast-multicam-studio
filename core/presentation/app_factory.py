"""
Fábrica y ensamblador de la aplicación aiohttp (Composition Root).
Inyecta las dependencias entre las capas de infraestructura, aplicación y presentación,
e integra el middleware global de trazabilidad y captura de excepciones en JSON.
"""

import os
import time
from aiohttp import web
from core.config import (
    STATIC_DIR, RECORDINGS_DIR, PORT, ANGULAR_DIST_DIR
)
from core.application import RecorderService, MarkersService, SignalingHub
from core.infrastructure.network import detect_primary_ip
from core.infrastructure.json_logger import log_event, log_exception
from core.presentation.controllers.recording_controller import RecordingController
from core.presentation.controllers.network_controller import NetworkController
from core.presentation.controllers.telemetry_controller import TelemetryController
from core.presentation.controllers.signaling_controller import SignalingController
from core.presentation.controllers.spa_controller import SpaController


@web.middleware
async def traceability_middleware(request: web.Request, handler):
    """
    Middleware global de trazabilidad:
    - Mide la latencia de cada petición HTTP.
    - Registra llamadas críticas a la API y accesos de cámaras móviles.
    - Captura cualquier excepción no controlada indicando exactamente archivo, línea, función y causa.
    """
    start_t = time.perf_counter()
    path = request.path
    method = request.method
    try:
        response = await handler(request)
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

        # Evitar saturar el log con el polling frecuente de telemetría/ping o chunks binarios
        noisy_paths = ("/api/telemetry", "/api/ping", "/api/record/chunk", "/api/logs")
        if not path.startswith(noisy_paths) and (path.startswith("/api/") or path.startswith("/cam/")):
            lvl = "WARN" if response.status >= 400 else "INFO"
            log_event(
                component="HTTP_ROUTER",
                message=f"{method} {path} -> HTTP {response.status} ({elapsed_ms} ms)",
                details={
                    "method": method,
                    "path": path,
                    "status": response.status,
                    "duration_ms": elapsed_ms,
                    "client_ip": request.remote,
                    "user_agent": request.headers.get("User-Agent", "")
                },
                level=lvl,
                category="HTTP_API",
                action=f"HTTP_{method}_{response.status}"
            )
        return response
    except web.HTTPException as http_exc:
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        if http_exc.status >= 400 and not path.endswith(".map"):
            log_event(
                component="HTTP_ROUTER",
                message=f"HTTPException {http_exc.status} en {method} {path}: {http_exc.reason}",
                details={
                    "method": method,
                    "path": path,
                    "status": http_exc.status,
                    "reason": http_exc.reason,
                    "duration_ms": elapsed_ms,
                    "client_ip": request.remote
                },
                level="WARN" if http_exc.status < 500 else "ERROR",
                category="HTTP_API",
                action=f"HTTP_ERR_{http_exc.status}"
            )
        raise
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        log_exception(
            component="HTTP_ROUTER",
            action=f"UNHANDLED_{method}",
            exc=exc,
            context_details={
                "method": method,
                "path": path,
                "duration_ms": elapsed_ms,
                "client_ip": request.remote
            }
        )
        raise


class ApplicationContainer:
    """Contenedor de Inversión de Control (IoC) para dependencias de backend."""
    def __init__(self):
        # 1. Servicios de Aplicación
        self.recorder_service = RecorderService(RECORDINGS_DIR)
        self.markers_service = MarkersService(RECORDINGS_DIR)
        self.signaling_hub = SignalingHub(lambda: detect_primary_ip()[0])

        # 2. Controladores de Presentación
        self.recording_controller = RecordingController(self.recorder_service, self.markers_service)
        self.network_controller = NetworkController(PORT)
        self.telemetry_controller = TelemetryController(RECORDINGS_DIR)
        self.signaling_controller = SignalingController(self.signaling_hub)
        self.spa_controller = SpaController(ANGULAR_DIST_DIR, STATIC_DIR)


def create_application(container: ApplicationContainer = None) -> web.Application:
    """Construye y enlaza la aplicación web aiohttp con sus controladores y middleware de trazabilidad."""
    if container is None:
        container = ApplicationContainer()

    # client_max_size=100MB para soportar streaming continuo de chunks binarios de video 1080p60 sin HTTP 413
    app = web.Application(middlewares=[traceability_middleware], client_max_size=100 * 1024 * 1024)
    app["container"] = container

    # 1. Rutas de Entrega SPA Frontend
    app.router.add_get("/", container.spa_controller.handle_index)
    app.router.add_get("/cam/{id}", container.spa_controller.handle_camera)

    # 2. Rutas de Diagnóstico, Telemetría y Matriz de Logs JSON
    app.router.add_get("/api/network", container.network_controller.handle_diagnostics)
    app.router.add_get("/api/connections", container.network_controller.handle_connections)
    app.router.add_post("/api/connections/adb-reverse", container.network_controller.handle_adb_reverse)
    app.router.add_post("/api/connections/open-hotspot", container.network_controller.handle_open_hotspot)
    app.router.add_get("/api/qr", container.network_controller.handle_qr)
    app.router.add_get("/api/ping", container.network_controller.handle_ping)
    app.router.add_get("/api/telemetry", container.telemetry_controller.handle_telemetry)
    app.router.add_get("/api/logs", container.telemetry_controller.handle_get_logs)
    app.router.add_post("/api/logs", container.telemetry_controller.handle_ingest_log)
    app.router.add_get("/api/logs/open-folder", container.telemetry_controller.handle_open_logs_folder)

    # 3. Rutas de Grabador Físico de Tomas y Marcadores
    app.router.add_post("/api/record/start", container.recording_controller.handle_start)
    app.router.add_post("/api/record/chunk", container.recording_controller.handle_chunk)
    app.router.add_post("/api/record/stop", container.recording_controller.handle_stop)
    app.router.add_post("/api/record/marker", container.recording_controller.handle_marker)
    app.router.add_get("/api/record/open-folder", container.recording_controller.handle_open_folder)

    # 4. WebSocket Hub de Señalización WebRTC
    app.router.add_get("/ws", container.signaling_controller.handle_ws)

    # 5. Assets Compilados de Angular
    container.spa_controller.register_angular_dist_routes(app)

    # 6. Fallbacks Estáticos Legacy
    app.router.add_static("/static/", STATIC_DIR, name="static")
    app.router.add_get("/app.js", lambda r: web.FileResponse(os.path.join(STATIC_DIR, "director", "app.js")))
    app.router.add_get("/jsqr.min.js", lambda r: web.FileResponse(os.path.join(STATIC_DIR, "mobile", "jsqr.min.js")))

    return app
