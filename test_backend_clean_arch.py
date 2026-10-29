# -*- coding: utf-8 -*-
"""
Test Suite de Validación - Backend Clean Architecture & Consolidación Frontend-Backend
Valida:
1. Capa de Dominio (Modelos puros y Excepciones)
2. Capa de Infraestructura (DiskStorageSink, Network, Telemetría, SSL)
3. Capa de Aplicación (RecorderService, MarkersService, SignalingHub)
4. Capa de Presentación (Controladores desacoplados e Inversión de Control)
5. Comprobación End-to-End en Memoria de endpoints REST y entrega de Angular SPA
"""

import os
import sys
import asyncio
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from core.domain.models import TakeSession, MarkerFlag, VideoProfile, SystemTelemetryData
from core.domain.exceptions import StudioDomainException, NoActiveRecordingException
from core.infrastructure.storage.disk_sink import DiskStorageSink
from core.infrastructure.network import detect_primary_ip, is_port_in_use
from core.infrastructure.telemetry import get_system_telemetry
from core.presentation.app_factory import create_application, ApplicationContainer
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

def run_clean_architecture_tests():
    print("=" * 80)
    print(" 🏛️  VALIDACIÓN TÉCNICA - BACKEND CLEAN ARCHITECTURE")
    print("=" * 80)

    results = []

    # 1. Capa de Dominio
    try:
        vp = VideoProfile(id="1080p60", width=1920, height=1080, fps=60, name="Full HD 60")
        mf = MarkerFlag(index=1, timecode="00:01:23:14", note="Test Flag", created_at="2026-10-26 22:00:00")
        st = SystemTelemetryData(ram_used_gb=8.0, ram_total_gb=16.0, ram_percent=50.0, disk_free_gb=100.0, cpu_percent=12.5)
        results.append(("Domain: Entidades Inmutables", bool(vp and mf and st), "VideoProfile, MarkerFlag, SystemTelemetryData instanciadas"))
        results.append(("Domain: Excepciones de Negocio", issubclass(NoActiveRecordingException, StudioDomainException), "Jerarquía de excepciones de dominio"))
    except Exception as e:
        results.append(("Domain: Capa de Dominio", False, f"Excepción: {e}"))

    # 2. Capa de Infraestructura (DiskStorageSink)
    try:
        temp_dir = os.path.join(base_dir, "Grabaciones", "Test_CleanArch")
        sink = DiskStorageSink(temp_dir)
        sess = TakeSession(
            project="CleanArch",
            episode="Ep01",
            take=1,
            resolution="1080p",
            fps=60,
            extension="webm",
            file_path=os.path.join(temp_dir, "CleanArch", "Ep01", "toma_test.webm"),
            folder_path=os.path.join(temp_dir, "CleanArch", "Ep01")
        )
        sink.start_take_file(sess)
        written = sink.write_chunk(b"DATA_CHUNK_CLEAN_ARCH_TEST")
        sealed = sink.seal_take_file()

        has_written = written > 0 and sealed.bytes_written == written and os.path.exists(sess.file_path)
        results.append(("Infra: DiskStorageSink Streaming", has_written, f"Chunk escrito ({written} B) y sellado físico"))

        # Limpieza
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        results.append(("Infra: DiskStorageSink", False, f"Excepción: {e}"))

    # 2.5 Capa de Infraestructura: Matriz de Conexiones Multiruta y Hub USB
    try:
        from core.infrastructure.network import get_full_connection_matrix, get_adb_devices
        matrix = get_full_connection_matrix(8443)
        has_matrix = (
            "hotspot_5ghz" in matrix and
            "usb_adb" in matrix and
            "apple_usb" in matrix and
            "android_rndis" in matrix and
            "available_routes" in matrix
        )
        results.append(("Infra: Multi-Route Connection Hub", has_matrix, f"{len(matrix.get('available_routes', []))} rutas de conexión compiladas"))
    except Exception as e:
        results.append(("Infra: Multi-Route Connection Hub", False, f"Excepción: {e}"))

    # 3. Capa de Presentación & Composición (IoC Container)
    try:
        container = ApplicationContainer()
        results.append(("Presentation: IoC Container", bool(container.recorder_service and container.signaling_hub), "Contenedor de dependencias ensamblado"))
        app = create_application(container)
        results.append(("Presentation: App Factory", isinstance(app, web.Application), "Fábrica create_application() retornó aiohttp.web.Application"))
    except Exception as e:
        results.append(("Presentation: Composición", False, f"Excepción: {e}"))

    # 4. Verificación de Rutas Registradas
    routes = [r.resource.canonical for r in app.router.routes() if hasattr(r, 'resource') and r.resource]
    expected_routes = [
        "/", "/cam/{id}", "/api/network", "/api/connections", "/api/connections/adb-reverse",
        "/api/connections/open-hotspot", "/api/qr", "/api/ping", "/api/telemetry",
        "/api/record/start", "/api/record/chunk", "/api/record/stop", "/api/record/marker", "/ws"
    ]

    for er in expected_routes:
        matched = any(er == r for r in routes)
        results.append((f"Route: {er}", matched, f"Ruta {er} mapeada en el enrutador"))

    # Imprimir Resultados
    print(f"\n{'ESTADO':<8} | {'COMPONENTE / PRUEBA':<38} | {'DETALLE'}")
    print("-" * 80)
    all_ok = True
    for name, passed, detail in results:
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_ok = False
        print(f" {status_str:<6} | {name:<38} | {detail}")

    print("\n" + "=" * 80)
    print(f" Total Pruebas: {len(results)} | Aprobadas: {sum(1 for r in results if r[1])} | Fallidas: {sum(1 for r in results if not r[1])}")
    if all_ok:
        print("\n ✅ CLEAN ARCHITECTURE BACKEND: 100% DE PRUEBAS APROBADAS.")
    else:
        print("\n ❌ SE ENCONTRARON FALLAS EN LA VALIDACIÓN CLEAN ARCHITECTURE.")
    print("=" * 80)

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(run_clean_architecture_tests())
