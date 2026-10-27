"""
Test Suite: Sprint 5 - Tarea 5.1 (Standalone Windows Packaging & Desktop App Mode).
Verifica:
1. Empaquetado de producción de `start_studio.exe` y estructura `_internal`.
2. Integración de bundles frontend compilados y brand assets en el ejecutable.
3. Módulo `desktop_launcher` y argumentos de ventana Chromium/Edge.
4. Resolución de rutas en `core/config.py` (sys.frozen vs dev mode).
5. Ejecución en vivo de `dist/start_studio/start_studio.exe` sirviendo API y frontend.
"""

import os
import sys
import time
import ssl
import json
import unittest
import subprocess
import urllib.request
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent
DIST_DIR = REPO_ROOT / "dist" / "start_studio"
EXE_PATH = DIST_DIR / "start_studio.exe"
PORTABLE_EXE_PATH = REPO_ROOT / "dist" / "TX-Studio-v1.0.0-Portable.exe"
MSI_INSTALLER_PATH = REPO_ROOT / "dist" / "TX-Studio-Setup-v1.0.0.msi"
INSTALLER_BAT_PATH = REPO_ROOT / "install_tx_studio.bat"
INTERNAL_DIR = DIST_DIR / "_internal"

class TestSprint5Packaging(unittest.TestCase):
    """Pruebas de la Tarea 5.1: Empaquetador Autónomo de Windows."""

    def test_01_standalone_executable_exists(self):
        """Verifica que start_studio.exe, TX-Studio-v1.0.0-Portable.exe, TX-Studio-Setup-v1.0.0.msi e install_tx_studio.bat existan."""
        self.assertTrue(EXE_PATH.exists(), f"No se encontró el ejecutable en {EXE_PATH}")
        size_mb = EXE_PATH.stat().st_size / (1024 * 1024)
        self.assertGreater(size_mb, 1.0, f"El ejecutable es sospechosamente pequeño: {size_mb:.2f} MB")

        self.assertTrue(PORTABLE_EXE_PATH.exists(), f"No se encontró el ejecutable portable único en {PORTABLE_EXE_PATH}")
        portable_mb = PORTABLE_EXE_PATH.stat().st_size / (1024 * 1024)
        self.assertGreater(portable_mb, 10.0, f"El ejecutable portable debe contener todo el runtime (>10MB): {portable_mb:.2f} MB")

        self.assertTrue(MSI_INSTALLER_PATH.exists(), f"No se encontró el instalador MSI oficial en {MSI_INSTALLER_PATH}")
        msi_mb = MSI_INSTALLER_PATH.stat().st_size / (1024 * 1024)
        self.assertGreater(msi_mb, 10.0, f"El instalador MSI debe empaquetar el sistema completo (>10MB): {msi_mb:.2f} MB")

        self.assertTrue(INSTALLER_BAT_PATH.exists(), "No se encontró el instalador install_tx_studio.bat")
        print(f"[OK] start_studio.exe ({size_mb:.2f} MB), Portable.exe ({portable_mb:.2f} MB) y Setup.msi ({msi_mb:.2f} MB) verificados")

    def test_02_internal_assets_bundled(self):
        """Verifica que los assets del frontend y static estén empaquetados en _internal."""
        self.assertTrue(INTERNAL_DIR.exists(), f"No se encontró la carpeta _internal en {INTERNAL_DIR}")
        
        # Frontend index
        frontend_index = INTERNAL_DIR / "frontend" / "dist" / "frontend" / "browser" / "index.html"
        self.assertTrue(frontend_index.exists(), f"Falta frontend index.html en {frontend_index}")
        
        # Brand assets inside internal frontend
        brand_svg = INTERNAL_DIR / "frontend" / "dist" / "frontend" / "browser" / "tx_studio_logoNaranja.svg"
        self.assertTrue(brand_svg.exists(), f"Falta logo SVG en frontend compilado: {brand_svg}")

        # Static assets
        static_dir = INTERNAL_DIR / "static"
        self.assertTrue(static_dir.exists(), f"Falta carpeta static en {static_dir}")
        print("[OK] Assets de Angular y marcas oficiales verificados en _internal")

    def test_03_desktop_launcher_module(self):
        """Verifica la lógica del lanzador de escritorio nativo (Chromium/Edge app mode)."""
        from core.infrastructure.desktop_launcher import find_chromium_executable, launch_desktop_window
        
        browser_path = find_chromium_executable()
        # En Windows 10/11 msedge.exe siempre está presente
        if sys.platform == "win32":
            self.assertIsNotNone(browser_path, "No se encontró ningún navegador Chromium/Edge en el sistema Windows")
            self.assertTrue(os.path.isfile(browser_path), f"El path no es un archivo: {browser_path}")
            print(f"[OK] Navegador de escritorio detectado: {browser_path}")

    def test_04_config_path_resolution(self):
        """Verifica que core.config maneje adecuadamente directorios persistentes, logs JSON y bundle."""
        from core.config import ROOT_DIR, BUNDLE_DIR, RECORDINGS_DIR, CERTS_DIR, LOGS_DIR
        from core.infrastructure.json_logger import init_json_logger
        
        self.assertTrue(os.path.isdir(ROOT_DIR), f"ROOT_DIR no existe: {ROOT_DIR}")
        self.assertTrue(os.path.isdir(BUNDLE_DIR), f"BUNDLE_DIR no existe: {BUNDLE_DIR}")
        self.assertTrue(os.path.isdir(RECORDINGS_DIR), f"RECORDINGS_DIR no existe: {RECORDINGS_DIR}")
        self.assertTrue(os.path.isdir(CERTS_DIR), f"CERTS_DIR no existe: {CERTS_DIR}")
        self.assertTrue(os.path.isdir(LOGS_DIR), f"LOGS_DIR no existe: {LOGS_DIR}")
        logger = init_json_logger(LOGS_DIR)
        logger.log("INFO", "TEST", "Verificación de registro JSON estructurado")
        try:
            raise ValueError("Simulación de error para matriz diagnóstica")
        except ValueError as e:
            logger.log_exception("TEST_COMPONENT", "SIMULATE_ERROR", e, {"test": True})
        self.assertTrue(os.path.isfile(logger.session_json_path), "Falta latest_session.json")
        self.assertTrue(os.path.isfile(logger.jsonl_path), "Falta tx_studio_events.jsonl")
        self.assertTrue(os.path.isfile(logger.error_matrix_path), "Falta error_matrix.json")
        print("[OK] Resolución de rutas y matriz de trazabilidad/errores JSON en core.config validada")

    def test_05_start_studio_bat_exists_and_configured(self):
        """Verifica que start_studio.bat esté listo para ejecución directa."""
        bat_path = REPO_ROOT / "start_studio.bat"
        self.assertTrue(bat_path.exists(), "start_studio.bat no existe en la raíz")
        
        content = bat_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("start_studio.exe", content, "El archivo .bat no referencia al ejecutable start_studio.exe")
        print("[OK] start_studio.bat verificado")

    def test_06_live_standalone_execution(self):
        """Lanza el ejecutable start_studio.exe en un puerto de prueba y valida su respuesta HTTP."""
        test_port = 8455
        cmd = [str(EXE_PATH), "--no-window", f"--port={test_port}"]
        
        print(f"[LIVE TEST] Iniciando proceso independiente: {EXE_PATH.name} en puerto {test_port}...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        server_ready = False
        start_time = time.time()
        api_data = None

        try:
            # Esperar hasta 8 segundos a que inicie y enlace el puerto
            while time.time() - start_time < 8.0:
                try:
                    req = urllib.request.urlopen(f"https://127.0.0.1:{test_port}/api/network", timeout=1.0, context=ctx)
                    if req.getcode() == 200:
                        server_ready = True
                        api_data = json.loads(req.read().decode("utf-8"))
                        break
                except Exception:
                    time.sleep(0.4)

            self.assertTrue(server_ready, f"El ejecutable no respondió en https://127.0.0.1:{test_port} tras 8 segundos")
            self.assertIsNotNone(api_data)
            self.assertIn("ip", api_data)
            print(f"[OK] Live API response desde start_studio.exe: IP={api_data.get('ip')}")

            # Validar que sirva la SPA frontend
            req_index = urllib.request.urlopen(f"https://127.0.0.1:{test_port}/", timeout=1.0, context=ctx)
            self.assertEqual(req_index.getcode(), 200)
            html_text = req_index.read().decode("utf-8")
            self.assertIn("<app-root", html_text)
            self.assertIn("TX-STUDIO", html_text)
            print("[OK] Standalone start_studio.exe sirvió index.html compilado con éxito")

        finally:
            print("[LIVE TEST] Terminando proceso de prueba...")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    unittest.main(verbosity=2)
