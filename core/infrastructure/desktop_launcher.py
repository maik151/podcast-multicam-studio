"""
Lanzador de Modo Aplicación de Escritorio Nativo (Edge / Chromium Runtime).
Permite abrir TX-STUDIO como una aplicación de escritorio independiente
sin barra de direcciones, sin controles de navegación y sin avisos de certificado local.
"""

import os
import sys
import subprocess
import threading
import time
import urllib.request
import ssl


def find_chromium_executable():
    """Busca ejecutables compatibles con modo ventana de aplicación de escritorio."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, r"Microsoft\Edge\Application\msedge.exe"))
        candidates.append(os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe"))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def launch_desktop_window(url: str, width: int = 1520, height: int = 920) -> bool:
    """Lanza la URL en una ventana de aplicación independiente sin barra de navegación."""
    # Para el monitor local del director en la PC, SIEMPRE usar 127.0.0.1 o localhost.
    # Esto garantiza que Chromium aplique --allow-insecure-localhost y nunca bloquee por SSL.
    local_url = url
    for prefix in ["https://192.168.", "https://10.", "https://172."]:
        if url.startswith(prefix):
            parts = url.split(":")
            if len(parts) >= 3:
                port_part = parts[2].split("/")[0]
                local_url = f"https://127.0.0.1:{port_part}"
            else:
                local_url = "https://127.0.0.1:8443"
            break

    browser_path = find_chromium_executable()
    if browser_path:
        try:
            # Perfil aislado para que no herede sesiones del Edge personal ni desactive el bypass de certificados
            profile_dir = os.path.expandvars(r"%LOCALAPPDATA%\TX-Studio\browser_profile")
            os.makedirs(profile_dir, exist_ok=True)

            cmd = [
                browser_path,
                f"--app={local_url}",
                f"--user-data-dir={profile_dir}",
                f"--window-size={width},{height}",
                "--ignore-certificate-errors",
                "--allow-insecure-localhost",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            subprocess.Popen(
                cmd,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return True
        except Exception as e:
            print(f"[DESKTOP] Error lanzando runtime de escritorio: {e}")

    # Fallback si no hay navegador Chromium disponible
    import webbrowser
    webbrowser.open(local_url)
    return False


def schedule_desktop_launch(url: str, delay_seconds: float = 1.0) -> None:
    """Inicia un hilo en segundo plano que espera el arranque del servidor y abre la ventana."""
    def _worker():
        time.sleep(delay_seconds)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        for _ in range(10):
            try:
                req = urllib.request.urlopen(f"{url}/api/network", timeout=1.0, context=ctx)
                if req.getcode() == 200:
                    req.read()
                    req.close()
                    break
            except Exception:
                time.sleep(0.25)

        print("[DESKTOP] 🖥️ Abriendo consola TX-STUDIO en modo aplicación de escritorio...")
        launch_desktop_window(url)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
