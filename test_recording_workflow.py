# -*- coding: utf-8 -*-
"""
Test Suite de Validación Integral:
1. Navegación Superior Sin Duplicados (CONSOLA EN VIVO / CONEXIONES + Archivo, Vista, Grabación, Herramientas)
2. Renderizado Program (PGM) y Preview (PVW) para cámaras USB DroidCam y preservación del Canvas en DOM
3. Flujo de Grabación por Grupo de Tomas (Proyecto ej. RUTA33 -> toma1.mp4, toma2.mp4, toma3.mp4...)
4. Protección anti-sobreescritura y Apertura Automática de Carpeta al finalizar grabación
"""

import os
import sys
import shutil
import unittest
from core.recording.recorder_service import RecorderService
from core.presentation.app_factory import create_application, ApplicationContainer

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class TestRecordingWorkflowAndPgmPvw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.join(BASE_DIR, "Grabaciones", "Test_Workflow_Ruta33")
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

        cls.html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.html"
        )
        cls.ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.ts"
        )
        cls.recorder_ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "services", "recorder.service.ts"
        )

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(cls.ts_path, "r", encoding="utf-8") as f:
            cls.ts = f.read()
        with open(cls.recorder_ts_path, "r", encoding="utf-8") as f:
            cls.recorder_ts = f.read()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. NAVEGACIÓN SUPERIOR SIN NOMBRES REPETIDOS
    # =========================================================================
    def test_top_bar_no_duplicate_estudio_or_conexiones(self):
        """Verifica que la barra superior use CONSOLA EN VIVO / CONEXIONES y menús Archivo, Vista, Grabación, Herramientas."""
        self.assertIn("CONSOLA EN VIVO", self.html)
        self.assertIn("toggleDesktopMenu('archivo'", self.html)
        self.assertIn("toggleDesktopMenu('vista'", self.html)
        self.assertIn("toggleDesktopMenu('grabacion'", self.html)
        self.assertIn("toggleDesktopMenu('herramientas'", self.html)
        self.assertNotIn("toggleDesktopMenu('estudio'", self.html)

    # =========================================================================
    # 2. FIX DE PANTALLA NEGRA EN PROGRAM (PGM) Y PREVIEW (PVW) CON DROIDCAM USB
    # =========================================================================
    def test_main_workspace_kept_alive_with_class_hidden(self):
        """Verifica que <main> use [class.hidden] en lugar de *ngIf para no destruir el <canvas #programCanvas>."""
        self.assertIn('[class.hidden]="activeWorkspaceView() !== \'studio\'"', self.html)
        self.assertNotIn('*ngIf="activeWorkspaceView() === \'studio\'"', self.html)

    def test_pgm_canvas_loop_resolves_connected_canvas_and_mjpeg_stream(self):
        """Verifica que startProgramCanvasLoop resuelva el canvas activo y dibuje streams MJPEG sin exigir liveImg.complete."""
        self.assertIn("Boolean(isDroidCam && liveImg && liveImg.naturalWidth > 0)", self.ts)
        self.assertNotIn("liveImg.naturalWidth > 0 && liveImg.complete", self.ts)
        self.assertIn('crossorigin="anonymous"', self.html)

    def test_pvw_monitor_renders_droidcam_usb_feed(self):
        """Verifica que el monitor de Preview (PVW) renderice la señal DroidCam USB cuando está activa."""
        self.assertIn("getDroidCamFeedUrl(switcher.previewCam())", self.html)
        self.assertIn("isDroidCamOnline(switcher.previewCam())", self.html)

    # =========================================================================
    # 3. FLUJO DE GRABACIÓN POR GRUPO DE TOMAS (PROYECTO RUTA33 -> toma1.mp4, toma2.mp4...)
    # =========================================================================
    def test_project_group_sequential_mp4_takes(self):
        """Verifica la creación del grupo de tomas RUTA33 y grabación de toma1.mp4, toma2.mp4, toma3.mp4 y toma4.mp4."""
        recorder = RecorderService(self.test_dir)

        # Crear proyecto RUTA33
        res_proj = recorder.create_project("RUTA33")
        self.assertEqual(res_proj["status"], "ok")
        self.assertEqual(res_proj["project"], "RUTA33")
        self.assertTrue(os.path.isdir(res_proj["folder"]))

        dummy_mp4_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + (b"\xab" * 8192)

        for idx in range(1, 5):
            take_label = f"toma{idx}"
            start_res = recorder.start_take(
                project="RUTA33",
                take=idx,
                resolution="1080p",
                fps=60,
                ext="mp4",
                custom_name=take_label
            )
            self.assertEqual(start_res["status"], "recording_started")
            self.assertEqual(start_res["file"], f"{take_label}.mp4")
            self.assertTrue(start_res["path"].endswith(os.path.join("RUTA33", f"{take_label}.mp4")))

            for _ in range(3):
                chunk_res = recorder.write_chunk(dummy_mp4_chunk)
                self.assertEqual(chunk_res["status"], "chunk_written")

            stop_res = recorder.stop_take(auto_open=False)
            self.assertEqual(stop_res["status"], "recording_saved")
            self.assertEqual(stop_res["file"], f"{take_label}.mp4")
            self.assertTrue(os.path.isfile(stop_res["path"]))
            self.assertGreater(stop_res["bytes"], 20000)

        # Verificar protección anti-sobreescritura si se vuelve a usar "toma1"
        dup_start = recorder.start_take(
            project="RUTA33",
            take=5,
            resolution="1080p",
            fps=60,
            ext="mp4",
            custom_name="toma1"
        )
        self.assertEqual(dup_start["file"], "toma1_02.mp4")
        recorder.write_chunk(dummy_mp4_chunk)
        recorder.stop_take(auto_open=False)

        # Verificar listado de proyectos y sugerencia de siguiente toma
        projects_info = recorder.list_projects()
        self.assertEqual(projects_info["status"], "ok")
        ruta33_info = next((p for p in projects_info["projects"] if p["name"] == "RUTA33"), None)
        self.assertIsNotNone(ruta33_info)
        self.assertEqual(ruta33_info["takes_count"], 5)
        self.assertEqual(ruta33_info["next_suggested_take"], "toma6")

    def test_routes_registered_in_app_factory(self):
        """Verifica que los nuevos endpoints /api/record/projects y /api/record/reveal estén registrados."""
        container = ApplicationContainer()
        app = create_application(container)
        routes = [r.resource.canonical for r in app.router.routes() if hasattr(r, "resource") and r.resource]
        self.assertIn("/api/record/projects", routes)
        self.assertIn("/api/record/reveal", routes)

    def test_angular_recorder_auto_increment_and_auto_open(self):
        """Verifica que RecorderService en Angular soporte autoIncrementTake, autoOpenFolderOnStop y formato mp4."""
        self.assertIn("autoIncrementTake = signal<boolean>(true)", self.recorder_ts)
        self.assertIn("autoOpenFolderOnStop = signal<boolean>(true)", self.recorder_ts)
        self.assertIn("incrementCustomTakeName()", self.recorder_ts)
        self.assertIn("ext: 'mp4'", self.recorder_ts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
