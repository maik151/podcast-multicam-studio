"""
Gestor de proceso del Microservicio de Video Nativo en Rust (tx-video-hub.exe).
Maneja el ciclo de vida (inicio, supervisión y apagado limpio) del sidecar de video en puerto 9100.
"""

import atexit
import json
import os
import subprocess
import sys
import urllib.request
from typing import Any, Dict, Optional

_PROCESS: Optional[subprocess.Popen] = None
VIDEO_HUB_PORT = 9100

def find_video_hub_binary() -> Optional[str]:
    """Localiza el binario compilado de tx-video-hub.exe."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(base_dir, "tools", "tx-video-hub.exe"),
        os.path.join(base_dir, "native", "tx-video-hub", "target", "release", "tx-video-hub.exe"),
        os.path.join(base_dir, "dist", "start_studio", "_internal", "tools", "tx-video-hub.exe"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "tools", "tx-video-hub.exe") if hasattr(sys, "_MEIPASS") else None,
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None

def is_video_hub_alive() -> bool:
    """Verifica si el microservicio está respondiendo peticiones HTTP en el puerto 9100."""
    try:
        url = f"http://127.0.0.1:{VIDEO_HUB_PORT}/status"
        req = urllib.request.Request(url, headers={"User-Agent": "tx-python-core"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def get_video_hub_status() -> Dict[str, Any]:
    """Consulta la telemetría en tiempo real del motor en Rust."""
    try:
        url = f"http://127.0.0.1:{VIDEO_HUB_PORT}/status"
        req = urllib.request.Request(url, headers={"User-Agent": "tx-python-core"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "offline", "error": str(e), "hub": "tx-video-hub"}

def ensure_video_hub_running() -> bool:
    """Asegura que el microservicio esté en ejecución en segundo plano."""
    global _PROCESS
    if is_video_hub_alive():
        return True

    exe_path = find_video_hub_binary()
    if not exe_path:
        print("[TX VIDEO-HUB] Aviso: Binario tx-video-hub.exe no encontrado.")
        return False

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        _PROCESS = subprocess.Popen(
            [exe_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags
        )
        print(f"[TX VIDEO-HUB] Microservicio nativo en Rust iniciado (PID: {_PROCESS.pid})")
        return True
    except Exception as e:
        print(f"[TX VIDEO-HUB] Error al iniciar subproceso: {e}")
        return False

def terminate_video_hub():
    """Detiene limpiamente el microservicio de Rust."""
    global _PROCESS
    if _PROCESS is not None:
        try:
            _PROCESS.terminate()
            _PROCESS.wait(timeout=1.0)
        except Exception:
            try:
                _PROCESS.kill()
            except Exception:
                pass
        _PROCESS = None

# Registrar apagado ordenado automático al salir de Python
atexit.register(terminate_video_hub)
