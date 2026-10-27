"""
Controlador HTTP de Telemetría y Trazabilidad de Logs (Presentation Layer).
Gestiona métricas de hardware en tiempo real y la matriz unificada de logs JSON
(Backend + Frontend Director + Cámaras Móviles PWA).
"""

import os
import sys
import subprocess
from aiohttp import web
from core.config import LOGS_DIR
from core.infrastructure.telemetry import get_system_telemetry
from core.infrastructure.json_logger import init_json_logger, log_event


class TelemetryController:
    def __init__(self, recordings_dir: str):
        self.recordings_dir = recordings_dir
        self.logger = init_json_logger(LOGS_DIR)

    async def handle_telemetry(self, request: web.Request) -> web.Response:
        metrics = get_system_telemetry(self.recordings_dir)
        return web.json_response(metrics)

    async def handle_ingest_log(self, request: web.Request) -> web.Response:
        """Recibe eventos estructurados o errores desde el Frontend Angular o las Cámaras Móviles."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON payload"}, status=400)

        entries = body if isinstance(body, list) else [body]
        recorded = 0
        for item in entries:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level", "INFO")).upper()
            source = str(item.get("source", "FRONTEND_UI")).upper()
            category = str(item.get("category", "UI_INTERACTION")).upper()
            component = str(item.get("component", "DIRECTOR_UI")).upper()
            action = str(item.get("action", "UI_EVENT")).upper()
            message = str(item.get("message", ""))
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            details["client_ip"] = request.remote

            log_event(
                component=component,
                message=message,
                details=details,
                level=level,
                category=category,
                source=source,
                action=action
            )
            recorded += 1

        return web.json_response({"status": "ok", "recorded": recorded})

    async def handle_get_logs(self, request: web.Request) -> web.Response:
        """Devuelve el resumen matricial de logs y errores de la sesión activa."""
        summary = self.logger.get_matrix_summary()
        return web.json_response(summary)

    async def handle_open_logs_folder(self, request: web.Request) -> web.Response:
        """Abre la carpeta de Logs JSON en el Explorador de Windows."""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            if sys.platform == "win32":
                subprocess.Popen(
                    ["explorer.exe", os.path.normpath(LOGS_DIR)],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            log_event(
                component="TELEMETRY_CTRL",
                message=f"Carpeta de logs abierta: {LOGS_DIR}",
                details={"path": LOGS_DIR},
                level="INFO",
                category="SYSTEM",
                action="OPEN_LOGS_FOLDER"
            )
            return web.json_response({"status": "ok", "path": LOGS_DIR})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)
