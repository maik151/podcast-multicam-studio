"""
Punto de entrada de Podcast Multicam Studio (Clean Architecture Core).
"""

import os
import sys
import asyncio
from aiohttp import web

from core.config import PORT, HOST, CERTS_DIR, setup_windows_console
from core.infrastructure.network import release_port_if_busy, detect_primary_ip, create_ssl_context
from core.presentation.app_factory import create_application

def _silence_proactor_reset(loop):
    """Suprime advertencias inofensivas de reset de socket en Windows (WinError 10054)."""
    orig_handler = loop.get_exception_handler()
    def _handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", 0) == 10054:
            return
        if orig_handler:
            orig_handler(loop, context)
        else:
            loop.default_exception_handler(context)
    loop.set_exception_handler(_handler)

def main():
    """Inicia el servidor local de broadcast en HTTPS / WebSockets."""
    setup_windows_console()

    # Configurar loop de asyncio para suprimir resets benignos en Windows
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    _silence_proactor_reset(loop)

    # Parsear argumentos opcionales de puerto
    port = PORT
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    # 1. Liberar socket si una instancia previa quedó colgada
    release_port_if_busy(port, auto_kill=True)

    # 2. Diagnóstico de Red y Adaptador Activo
    primary_ip, iface_desc = detect_primary_ip()
    base_url = f"https://{primary_ip}:{port}"

    print("=" * 65)
    print(" 🎙️ PODCAST MULTICAM STUDIO // CLEAN ARCHITECTURE BACKEND")
    print("=" * 65)
    print(f" [ESTADO]  Servidor Local Seguro Activo (TLS v1.3)")
    print(f" [RED]     {iface_desc}")
    print(f" [CONSOLA] {base_url}/")
    print(f" [CÁMARAS] {base_url}/cam/1  (QR disponible en la consola)")
    print("=" * 65)

    # 3. Contexto SSL Seguro X.509
    ssl_context = create_ssl_context(CERTS_DIR)

    # 4. Construir la Aplicación con Clean Architecture
    app = create_application()

    # 5. Lanzar ventana de escritorio nativa (Edge App Mode) si no se especifica --no-window
    if "--no-window" not in sys.argv:
        from core.infrastructure.desktop_launcher import schedule_desktop_launch
        schedule_desktop_launch(base_url, delay_seconds=1.2)

    # 6. Iniciar Servidor Asíncrono
    web.run_app(
        app,
        host=HOST,
        port=port,
        ssl_context=ssl_context,
        print=None
    )

if __name__ == "__main__":
    main()
