"""
Test Suite Riguroso - Sprint 3: Motor de Grabación Robusto a Disco & Marcadores
Tareas 3.1, 3.2 y 3.3: Configuración de códec GPU, Tomas Continuas y Marcadores REC FLAG
"""

import unittest
import os
import re
import json
import shutil
from core.recording.recorder_service import RecorderService as BackendRecorderService
from core.recording.markers_service import MarkersService as BackendMarkersService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestSprint3RecordingEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Rutas a los archivos del motor de grabación
        cls.recorder_service_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "services", "recorder.service.ts"
        )
        cls.director_component_ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.ts"
        )
        cls.models_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "models", "studio.models.ts"
        )
        cls.app_js_path = os.path.join(BASE_DIR, "static", "director", "app.js")
        cls.test_recordings_dir = os.path.join(BASE_DIR, "Grabaciones", "Test_Sprint3_Takes")

        with open(cls.recorder_service_path, "r", encoding="utf-8") as f:
            cls.recorder_ts = f.read()
        with open(cls.director_component_ts_path, "r", encoding="utf-8") as f:
            cls.director_ts = f.read()
        with open(cls.models_path, "r", encoding="utf-8") as f:
            cls.models_ts = f.read()
        with open(cls.app_js_path, "r", encoding="utf-8") as f:
            cls.app_js = f.read()

    @classmethod
    def tearDownClass(cls):
        # Limpieza de carpeta de pruebas
        if os.path.exists(cls.test_recordings_dir):
            try:
                shutil.rmtree(cls.test_recordings_dir)
            except Exception:
                pass

    # =========================================================================
    # --- TAREA 3.1: CONFIGURACIÓN DE CÓDEC ÓPTIMO POR HARDWARE ---
    # =========================================================================
    def test_h264_is_first_candidate_in_angular(self):
        """Verifica que H.264 (acelerado por NVENC/QuickSync) sea el candidato #1 en Angular."""
        idx_h264 = self.recorder_ts.find('h264,opus')
        idx_vp9 = self.recorder_ts.find('vp9,opus')
        self.assertNotEqual(idx_h264, -1, "Debe existir candidato H.264")
        self.assertNotEqual(idx_vp9, -1, "Debe existir candidato VP9")
        self.assertLess(idx_h264, idx_vp9, "H.264 DEBE evaluarse antes que VP9 para activar aceleración GPU")

    def test_h264_is_first_candidate_in_static_app_js(self):
        """Verifica que H.264 sea el candidato #1 en static/director/app.js."""
        idx_h264 = self.app_js.find('h264,opus')
        idx_vp9 = self.app_js.find('vp9,opus')
        self.assertNotEqual(idx_h264, -1, "Debe existir candidato H.264 en app.js")
        self.assertNotEqual(idx_vp9, -1, "Debe existir candidato VP9 en app.js")
        self.assertLess(idx_h264, idx_vp9, "H.264 DEBE evaluarse antes que VP9 en app.js")

    def test_codec_hierarchy_coverage(self):
        """Verifica la jerarquía completa: H.264 -> VP9 -> VP8 -> WebM -> MP4."""
        self.assertIn('h264,opus', self.recorder_ts)
        self.assertIn('vp9,opus', self.recorder_ts)
        self.assertIn('vp8,opus', self.recorder_ts)
        self.assertIn('video/webm', self.recorder_ts)
        self.assertIn('video/mp4', self.recorder_ts)

    def test_video_profiles_definition(self):
        """Verifica la definición de perfiles 1080p60, 2K60 y 4K60 en studio.models.ts."""
        self.assertIn("'1080p60'", self.models_ts)
        self.assertIn("'2K60'", self.models_ts)
        self.assertIn("'4K60'", self.models_ts)
        self.assertIn("VIDEO_PROFILES", self.models_ts)

    def test_calibrated_bitrates(self):
        """Verifica que 1080p60 use 8 Mbps video y 192 kbps audio."""
        self.assertIn("8_000_000", self.models_ts)
        self.assertIn("192_000", self.models_ts)
        self.assertIn("16_000_000", self.models_ts)
        self.assertIn("256_000", self.models_ts)
        self.assertIn("35_000_000", self.models_ts)
        self.assertIn("320_000", self.models_ts)

    def test_recorder_service_signals(self):
        """Verifica que RecorderService exponga señales de profile, codec y aceleración."""
        self.assertIn("currentProfile = signal<VideoProfile>", self.recorder_ts)
        self.assertIn("activeCodec = signal<string>", self.recorder_ts)
        self.assertIn("isHardwareAccelerated = signal<boolean>", self.recorder_ts)
        self.assertIn("setVideoProfile", self.recorder_ts)

    def test_media_recorder_options_pass_bitrates(self):
        """Verifica que MediaRecorderOptions configure videoBitsPerSecond y audioBitsPerSecond."""
        self.assertIn("videoBitsPerSecond: profile.videoBitrate", self.recorder_ts)
        self.assertIn("audioBitsPerSecond: profile.audioBitrate", self.recorder_ts)
        self.assertIn("audioBitsPerSecond: 192000", self.app_js)

    # =========================================================================
    # --- TAREA 3.2: GRABACIÓN POR TOMAS NUMERADAS CONTINUAS (TAKE CHUNKING) ---
    # =========================================================================
    def test_backend_continuous_take_chunking_3_takes(self):
        """Verifica la grabación secuencial de 3 tomas consecutivas en disco."""
        recorder = BackendRecorderService(self.test_recordings_dir)
        proj = "Podcast_Master"
        ep = "Episodio_01"
        dummy_chunk = b"\x1a\x45\xdf\xa3" + b"\x00" * 4096  # Chunk binario simulado

        saved_files = []
        for take_num in range(1, 4):
            # 1. Iniciar Toma
            res_start = recorder.start_take(
                project=proj, episode=ep, take=take_num, resolution="1080p", fps=60, ext="webm"
            )
            self.assertEqual(res_start["status"], "recording_started")
            self.assertEqual(res_start["take"], take_num)
            self.assertTrue(res_start["file"].startswith(f"Toma_{take_num:02d}_1080p_60fps_"))

            # 2. Escribir Chunks binarios continuos
            for _ in range(5):
                res_chunk = recorder.write_chunk(dummy_chunk)
                self.assertEqual(res_chunk["status"], "chunk_written")

            # 3. Sellar Toma
            res_stop = recorder.stop_take()
            self.assertEqual(res_stop["status"], "recording_saved")
            self.assertGreater(res_stop["bytes"], 0)
            self.assertTrue(os.path.exists(res_stop["path"]))
            saved_files.append(res_stop["path"])

        # Verificar que las 3 tomas coexisten en la carpeta de destino
        self.assertEqual(len(saved_files), 3)
        for f in saved_files:
            self.assertTrue(os.path.exists(f))
            self.assertGreater(os.path.getsize(f), 20000)

    def test_backend_auto_seal_safeguard(self):
        """Verifica que abrir una nueva toma sin cerrar la anterior la selle de forma segura."""
        recorder = BackendRecorderService(self.test_recordings_dir)
        recorder.start_take(project="AutoSealTest", episode="Ep_01", take=1)
        recorder.write_chunk(b"DATA_TAKE_1")
        take1_path = recorder.current_recording_path

        # Iniciar toma 2 sin llamar a stop_take() explícitamente
        recorder.start_take(project="AutoSealTest", episode="Ep_01", take=2)
        recorder.write_chunk(b"DATA_TAKE_2")
        recorder.stop_take()

        # El archivo de la toma 1 debió ser cerrado y preservado
        self.assertTrue(os.path.exists(take1_path))
        self.assertGreater(os.path.getsize(take1_path), 0)

    def test_angular_recorder_service_take_management(self):
        """Verifica que el servicio de Angular incremente take tras sellar y ofrezca setters."""
        self.assertIn("take: s.take + 1", self.recorder_ts)
        self.assertIn("setProject(project: string)", self.recorder_ts)
        self.assertIn("setEpisode(episode: string)", self.recorder_ts)
        self.assertIn("setTake(take: number)", self.recorder_ts)
        self.assertIn("resetTakes()", self.recorder_ts)

    def test_angular_recorder_service_safe_stop_await(self):
        """Verifica que stopRecording espere onstop y pendingChunkUploads antes de sellar."""
        self.assertIn("mediaRecorder.requestData()", self.recorder_ts)
        self.assertIn("mediaRecorder.onstop", self.recorder_ts)
        self.assertIn("await Promise.all(this.pendingChunkUploads)", self.recorder_ts)

    # =========================================================================
    # --- TAREA 3.3: SISTEMA DE MARCADORES DE MOMENTOS CLAVE (REC FLAG [R]) ---
    # =========================================================================
    def test_markers_service_dual_export_txt_and_json(self):
        """Verifica la generación dual TXT y JSON de marcadores con código de tiempo exacto."""
        markers_service = BackendMarkersService(self.test_recordings_dir)
        proj = "Markers_Test"
        ep = "Ep_01"
        take_num = 1

        # Registrar 3 marcadores en momentos clave
        m1 = markers_service.add_marker(
            project=proj, episode=ep, take=take_num, timecode_str="00:02:15:10", note="Presentación del invitado", count=1
        )
        m2 = markers_service.add_marker(
            project=proj, episode=ep, take=take_num, timecode_str="00:05:42:00", note="Debate sobre IA para Short", count=2
        )
        m3 = markers_service.add_marker(
            project=proj, episode=ep, take=take_num, timecode_str="00:08:19:25", note="Anécdota divertida para Reels", count=3
        )

        self.assertEqual(m1["status"], "marker_added")
        self.assertEqual(m2["total"], 2)
        self.assertEqual(m3["total"], 3)

        # Verificar archivos físicos generados
        folder = os.path.join(self.test_recordings_dir, proj, ep)
        txt_file = os.path.join(folder, f"Toma_{take_num:02d}_Marcadores.txt")
        json_file = os.path.join(folder, f"Toma_{take_num:02d}_Marcadores.json")

        self.assertTrue(os.path.exists(txt_file), "Debe existir archivo TXT de marcadores")
        self.assertTrue(os.path.exists(json_file), "Debe existir archivo JSON de marcadores")

        # Contenido TXT
        with open(txt_file, "r", encoding="utf-8") as f:
            txt_content = f.read()
        self.assertIn("[00:02:15:10] - FLAG #1: Presentación del invitado", txt_content)
        self.assertIn("[00:05:42:00] - FLAG #2: Debate sobre IA para Short", txt_content)
        self.assertIn("[00:08:19:25] - FLAG #3: Anécdota divertida para Reels", txt_content)

        # Contenido JSON estructurado
        with open(json_file, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        self.assertEqual(len(json_data), 3)
        self.assertEqual(json_data[0]["timecode"], "00:02:15:10")
        self.assertEqual(json_data[1]["timecode"], "00:05:42:00")
        self.assertEqual(json_data[2]["timecode"], "00:08:19:25")
        self.assertEqual(json_data[2]["index"], 3)

        # Método de consulta get_markers
        queried = markers_service.get_markers(proj, ep, take_num)
        self.assertEqual(len(queried), 3)

    def test_angular_recorder_service_add_marker_flag_payload(self):
        """Verifica que el servicio de Angular envíe el payload completo al backend."""
        self.assertIn("project: state.project", self.recorder_ts)
        self.assertIn("episode: state.episode", self.recorder_ts)
        self.assertIn("take: state.take", self.recorder_ts)
        self.assertIn("timecode: state.timecode", self.recorder_ts)
        self.assertIn("markers.update", self.recorder_ts)

    def test_keyboard_shortcut_r_and_ctrl_r(self):
        """Verifica que la tecla 'R' dispare marcador y 'Ctrl+R' conmute grabación."""
        self.assertIn("e.key === 'r' || e.key === 'R'", self.director_ts)
        self.assertIn("if (e.ctrlKey)", self.director_ts)
        self.assertIn("this.onToggleRecording()", self.director_ts)
        self.assertIn("this.onAddMarkerFlag()", self.director_ts)
        # En static app.js también
        self.assertIn("e.key === 'r' || e.key === 'R'", self.app_js)
        self.assertIn("addMarkerFlag()", self.app_js)

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print(" 📼 INICIANDO VALIDACIÓN TÉCNICA RIGUROSA - SPRINT 3 (TAREAS 3.1, 3.2, 3.3)")
    print("=" * 80)
    unittest.main(verbosity=2)
