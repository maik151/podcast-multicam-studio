"""
Configuración centralizada y arquitectura de directorios de sistema para TX-STUDIO.
En modo instalado de Windows (sys.frozen), almacena grabaciones, logs JSON y certificados
en C:\\Users\\<Usuario>\\Documents\\TX-STUDIO\\.
"""

import os
import sys

# Rutas del Binario / Bundle
if getattr(sys, "frozen", False):
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BASE_DIR = BUNDLE_DIR

ROOT_DIR = BASE_DIR

# Directorio de Documentos del Usuario para Aplicación de Sistema Windows
def _resolve_user_data_dir() -> str:
    if getattr(sys, "frozen", False):
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "TX-STUDIO")
        try:
            os.makedirs(docs_dir, exist_ok=True)
            return docs_dir
        except Exception:
            pass
    return BASE_DIR

USER_DATA_DIR = _resolve_user_data_dir()

# Los assets estáticos y compilados se leen del bundle empaquetado o del repo
ANGULAR_DIST_DIR = os.path.join(BUNDLE_DIR, "frontend", "dist", "frontend", "browser")
if not os.path.exists(ANGULAR_DIST_DIR):
    ANGULAR_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist", "frontend", "browser")

STATIC_DIR = os.path.join(BUNDLE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(BASE_DIR, "static")

# Directorios persistentes del usuario (Documentos\TX-STUDIO\ en producción)
CERTS_DIR = os.path.join(USER_DATA_DIR, "certs")
RECORDINGS_DIR = os.path.join(USER_DATA_DIR, "Grabaciones")
LOGS_DIR = os.path.join(USER_DATA_DIR, "Logs")

for _d in (CERTS_DIR, RECORDINGS_DIR, LOGS_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception:
        pass

try:
    from core.infrastructure.json_logger import init_json_logger
    SYSTEM_LOGGER = init_json_logger(LOGS_DIR)
except Exception:
    SYSTEM_LOGGER = None

# Parámetros de Red y Servidor
PORT = 8443
HOST = "0.0.0.0"

# Perfiles de Calidad de Video
PROFILES = {
    "1080p60": {"width": 1920, "height": 1080, "fps": 60, "name": "1080p @ 60 FPS (Broadcast)"},
    "4k30": {"width": 3840, "height": 2160, "fps": 30, "name": "2160p @ 30 FPS (4K Ultra)"},
    "1080p30": {"width": 1920, "height": 1080, "fps": 30, "name": "1080p @ 30 FPS (Low CPU)"}
}

DEFAULT_PROFILE = "1080p60"

def setup_windows_console():
    """Configura codificación UTF-8 y redirige salidas al registro estructurado JSONL."""
    if sys.platform == "win32":
        try:
            if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        from core.infrastructure.json_logger import init_json_logger, _StreamToJsonAdapter
        logger = init_json_logger(LOGS_DIR)
        if not isinstance(sys.stdout, _StreamToJsonAdapter):
            sys.stdout = _StreamToJsonAdapter(logger, "INFO", sys.stdout)
        if not isinstance(sys.stderr, _StreamToJsonAdapter):
            sys.stderr = _StreamToJsonAdapter(logger, "ERROR", sys.stderr)
    except Exception:
        pass
