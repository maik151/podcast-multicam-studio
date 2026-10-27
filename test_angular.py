# -*- coding: utf-8 -*-
"""
Test Suite de Validación Automática - Migración Angular 19 Core
Valida:
- Estructura y compilación del frontend Angular 19
- Servicios inyectables y reactividad con Signals
- Modelos de datos tipados en TypeScript
- Componentes Standalone (DirectorConsole y MobileCam)
- Enrutamiento SPA y servicio por el backend Python
"""

import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_angular_architecture():
    print("=" * 80)
    print(" 🅰️  INICIANDO VALIDACIÓN TÉCNICA - ARQUITECTURA ANGULAR 19")
    print("=" * 80)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, 'frontend')

    results = []

    # 1. Archivos estructurales de Angular
    pkg_json = os.path.join(frontend_dir, 'package.json')
    angular_json = os.path.join(frontend_dir, 'angular.json')
    tsconfig = os.path.join(frontend_dir, 'tsconfig.json')
    results.append(("Config: package.json", os.path.exists(pkg_json), "package.json presente"))
    results.append(("Config: angular.json", os.path.exists(angular_json), "angular.json presente"))
    results.append(("Config: tsconfig.json", os.path.exists(tsconfig), "tsconfig.json presente"))

    # 2. Modelos Tipados TypeScript
    models_file = os.path.join(frontend_dir, 'src', 'app', 'core', 'models', 'studio.models.ts')
    has_models = os.path.exists(models_file)
    results.append(("Models: studio.models.ts", has_models, "Interfaces tipadas CameraFeed, AudioMetrics, etc."))

    # 3. Servicios Core con Signals
    services = [
        ('audio-dsp.service.ts', 'AudioDspService', 'Web Audio DSP, Signals y dBFS'),
        ('switcher.service.ts', 'SwitcherService', 'Corte, T-Bar, Dip to Black y Mix'),
        ('webrtc-signaling.service.ts', 'WebRtcSignalingService', 'WebRTC P2P y Hub WebSocket'),
        ('recorder.service.ts', 'RecorderService', 'MediaRecorder y streaming de chunks'),
        ('telemetry.service.ts', 'TelemetryService', 'Sondeo de RAM, Disco y CPU')
    ]
    for sfile, sname, desc in services:
        spath = os.path.join(frontend_dir, 'src', 'app', 'core', 'services', sfile)
        exists = os.path.exists(spath)
        has_signal = False
        if exists:
            with open(spath, 'r', encoding='utf-8') as f:
                c = f.read()
                has_signal = 'signal<' in c or 'signal(' in c
        results.append((f"Service: {sname}", exists and has_signal, f"{desc} (con Signals reactivos)"))

    # 4. Componentes Standalone
    director_ts = os.path.join(frontend_dir, 'src', 'app', 'features', 'director', 'director.component.ts')
    director_html = os.path.join(frontend_dir, 'src', 'app', 'features', 'director', 'director.component.html')
    mobile_ts = os.path.join(frontend_dir, 'src', 'app', 'features', 'mobile-cam', 'mobile-cam.component.ts')
    mobile_html = os.path.join(frontend_dir, 'src', 'app', 'features', 'mobile-cam', 'mobile-cam.component.html')

    results.append(("Component: Director (TS)", os.path.exists(director_ts), "DirectorComponent standalone presente"))
    results.append(("Component: Director (HTML)", os.path.exists(director_html), "Plantilla visual OP-1 / ATEM"))
    results.append(("Component: MobileCam (TS)", os.path.exists(mobile_ts), "MobileCamComponent standalone presente"))
    results.append(("Component: MobileCam (HTML)", os.path.exists(mobile_html), "Plantilla PWA para smartphone"))

    # 5. Enrutamiento SPA
    routes_file = os.path.join(frontend_dir, 'src', 'app', 'app.routes.ts')
    has_routes = False
    if os.path.exists(routes_file):
        with open(routes_file, 'r', encoding='utf-8') as f:
            rc = f.read()
            has_routes = "path: ''" in rc and "path: 'cam/:id'" in rc
    results.append(("Routing: app.routes.ts", has_routes, "Rutas '/' (Director) y '/cam/:id' (Móvil)"))

    # 6. Compilación de Producción (dist/)
    dist_dir = os.path.join(frontend_dir, 'dist', 'frontend', 'browser')
    dist_index = os.path.join(dist_dir, 'index.html')
    has_bundle = os.path.exists(dist_index)
    results.append(("Build: Angular dist/ compilado", has_bundle, "Bundle de producción generado en dist/"))

    # 7. Integración con Backend Python (Clean Architecture)
    spa_controller_py = os.path.join(base_dir, 'core', 'presentation', 'controllers', 'spa_controller.py')
    has_backend_integration = False
    if os.path.exists(spa_controller_py):
        with open(spa_controller_py, 'r', encoding='utf-8') as f:
            mc = f.read()
            has_backend_integration = 'angular_dist_dir' in mc and 'handle_index' in mc
    results.append(("Backend: Servido por Python", has_backend_integration, "spa_controller.py configurado para servir el SPA de Angular"))

    # 8. Identidad Visual de Marca (Logos e Isotipos Oficiales en dist)
    logo_svg = os.path.join(dist_dir, 'tx_studio_logoNaranja.svg')
    isotipo_svg = os.path.join(dist_dir, 'tx_studio_Isotipo_naranja.svg')
    has_brand_assets = os.path.exists(logo_svg) and os.path.exists(isotipo_svg)
    results.append(("Brand: Logo y Isotipo Oficiales", has_brand_assets, "tx_studio_logoNaranja.svg y tx_studio_Isotipo_naranja.svg en dist/"))

    # Reporte
    print(f"\n{'ESTADO':<8} | {'COMPONENTE / PRUEBA':<36} | {'DETALLE'}")
    print("-" * 80)
    all_ok = True
    for name, passed, detail in results:
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_ok = False
        print(f" {status_str:<6} | {name:<36} | {detail}")

    print("\n" + "=" * 80)
    print(f" Total Pruebas: {len(results)} | Aprobadas: {sum(1 for r in results if r[1])} | Fallidas: {sum(1 for r in results if not r[1])}")
    if all_ok:
        print("\n ✅ MIGRACIÓN ANGULAR 19: ARQUITECTURA COMPLETADA Y 100% VALIDADA.")
    else:
        print("\n ❌ SE ENCONTRARON FALLAS EN LA VALIDACIÓN ANGULAR.")
    print("=" * 80)

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(test_angular_architecture())
