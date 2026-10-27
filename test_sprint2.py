"""
Test Suite Riguroso - Sprint 2: Motor de Switcher, Composición Visual y Transiciones
Tareas 2.1, 2.2 y 2.4: Transición Dip to Black, Mix Suave, T-Bar Virtual y Feedback de Teclado
"""

import unittest
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestSprint2SwitcherTBarAndKeyboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Rutas a los archivos clave
        cls.switcher_service_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "services", "switcher.service.ts"
        )
        cls.director_component_ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.ts"
        )
        cls.director_component_html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.html"
        )
        cls.app_js_path = os.path.join(BASE_DIR, "static", "director", "app.js")
        cls.index_html_path = os.path.join(BASE_DIR, "static", "director", "index.html")

        with open(cls.switcher_service_path, "r", encoding="utf-8") as f:
            cls.switcher_ts = f.read()
        with open(cls.director_component_ts_path, "r", encoding="utf-8") as f:
            cls.director_ts = f.read()
        with open(cls.director_component_html_path, "r", encoding="utf-8") as f:
            cls.director_html = f.read()
        with open(cls.app_js_path, "r", encoding="utf-8") as f:
            cls.app_js = f.read()
        with open(cls.index_html_path, "r", encoding="utf-8") as f:
            cls.index_html = f.read()

    # =========================================================================
    # --- TAREA 2.1: DIP TO BLACK Y MIX SUAVE EN CANVAS ---
    # =========================================================================
    def test_switcher_service_signals_dip_to_black(self):
        """Verifica que SwitcherService exponga las señales de Dip to Black."""
        self.assertIn("isDipToBlack = signal<boolean>(false)", self.switcher_ts)
        self.assertIn("dipProgress = signal<number>(0.0)", self.switcher_ts)
        self.assertIn("dipTargetCam = signal<number>(1)", self.switcher_ts)

    def test_switcher_service_dip_timing_and_phases(self):
        """Verifica que la duración sea de 600ms y conmute en el punto medio (50%)."""
        self.assertIn("dipDuration = 600", self.switcher_ts)
        self.assertIn("progress >= 0.5", self.switcher_ts)
        self.assertIn("this.activeCam.set(target)", self.switcher_ts)

    def test_switcher_service_smooth_mix(self):
        """Verifica la lógica de interpolación para transiciones Mix / Crossfade."""
        self.assertIn("transitionProgress = signal<number>(1.0)", self.switcher_ts)
        self.assertIn("setTbarProgress", self.switcher_ts)
        self.assertIn("animateFade", self.switcher_ts)

    def test_director_canvas_dip_to_black_rendering(self):
        """Verifica que el bucle de renderizado ejecute las dos fases de Dip to Black."""
        self.assertIn("if (this.switcher.isDipToBlack())", self.director_ts)
        self.assertIn("ctx.fillStyle = '#000000'", self.director_ts)
        self.assertIn("fadeOut = 1.0 - (dipProg / 0.5)", self.director_ts)
        self.assertIn("fadeIn = (dipProg - 0.5) / 0.5", self.director_ts)

    def test_director_canvas_smooth_mix_interpolation(self):
        """Verifica que el cross-dissolve interpole alpha entre cámara previa y activa."""
        self.assertIn("1.0 - progress", self.director_ts)
        self.assertIn("progress", self.director_ts)
        self.assertIn("drawVideoOrPattern(prevVid, prevCam, 1.0 - progress)", self.director_ts)
        self.assertIn("drawVideoOrPattern(activeVid, activeCam, progress)", self.director_ts)

    def test_director_keyboard_shortcut_d(self):
        """Verifica que la tecla 'D' o 'd' dispare la transición Dip to Black."""
        match = re.search(r"e\.key === 'd' \|\| e\.key === 'D'", self.director_ts)
        self.assertIsNotNone(match, "Debe existir listener para la tecla D")
        self.assertIn("triggerDipToBlack()", self.director_ts)

    def test_app_js_dip_to_black_logic(self):
        """Verifica que static/director/app.js implemente las dos fases de Dip to Black."""
        self.assertIn("if (isDipToBlack)", self.app_js)
        self.assertIn("progress < 0.5", self.app_js)
        self.assertIn("fadeOut = 1.0 - (progress / 0.5)", self.app_js)
        self.assertIn("fadeIn = (progress - 0.5) / 0.5", self.app_js)
        self.assertIn("activeCam = dipTargetCam", self.app_js)

    def test_app_js_smooth_mix_interpolation(self):
        """Verifica que static/director/app.js ejecute la disolvencia suave."""
        self.assertIn("transitionProgress < 1.0", self.app_js)
        self.assertIn("1.0 - transitionProgress", self.app_js)
        self.assertIn("drawCamFeed(ctx, prevVideo, prevCamId, 1.0 - transitionProgress", self.app_js)
        self.assertIn("drawCamFeed(ctx, activeVideo, activeCam, transitionProgress", self.app_js)

    def test_app_js_keyboard_shortcut_d(self):
        """Verifica que la tecla 'D' dispare triggerDipToBlack en app.js."""
        match = re.search(r"e\.key === 'd' \|\| e\.key === 'D'", self.app_js)
        self.assertIsNotNone(match)
        self.assertIn("triggerDipToBlack()", self.app_js)

    # =========================================================================
    # --- TAREA 2.2: T-BAR VIRTUAL CON CONTROL POR ARRASTRE Y TÁCTIL ---
    # =========================================================================
    def test_tbar_signals_in_switcher_service(self):
        """Verifica que SwitcherService exponga isTbarActive y tbarProgress."""
        self.assertIn("isTbarActive = signal<boolean>(false)", self.switcher_ts)
        self.assertIn("tbarProgress = signal<number>(0.0)", self.switcher_ts)
        self.assertIn("commitTbarTransition", self.switcher_ts)
        self.assertIn("cancelTbarTransition", self.switcher_ts)

    def test_tbar_commit_logic_when_reaching_end(self):
        """Verifica que commitTbarTransition conmute la cámara al llegar al final."""
        self.assertIn("prog >= 0.85", self.switcher_ts)
        self.assertIn("this.activeCam.set(target)", self.switcher_ts)
        self.assertIn("this.previewCam.set(oldActive)", self.switcher_ts)

    def test_director_canvas_tbar_manual_mixing(self):
        """Verifica que el canvas mezcle PGM y PVW proporcionalmente al arrastrar el T-Bar."""
        self.assertIn("if (isTbar)", self.director_ts)
        self.assertIn("drawVideoOrPattern(activeVid, activeCam, 1.0 - tProg)", self.director_ts)
        self.assertIn("drawVideoOrPattern(previewVid, previewCam, tProg)", self.director_ts)

    def test_director_html_tbar_elements(self):
        """Verifica la presencia de elementos táctiles del T-Bar en la plantilla Angular."""
        self.assertIn('id="tbar-track"', self.director_html)
        self.assertIn('id="tbar-fill"', self.director_html)
        self.assertIn('id="tbar-slider"', self.director_html)
        self.assertIn('id="tbar-handle"', self.director_html)
        self.assertIn('onTbarMouseDown', self.director_html)
        self.assertIn('onTbarTouchStart', self.director_html)

    def test_director_component_mouse_and_touch_listeners(self):
        """Verifica los controladores de ratón y gestos táctiles en DirectorComponent."""
        self.assertIn("onTbarMouseDown", self.director_ts)
        self.assertIn("onTbarTouchStart", self.director_ts)
        self.assertIn("onTbarTouchMove", self.director_ts)
        self.assertIn("onTbarTouchEnd", self.director_ts)
        self.assertIn("updateTbarFromPointer", self.director_ts)

    def test_static_index_html_tbar_elements(self):
        """Verifica la presencia de elementos del T-Bar en index.html estático."""
        self.assertIn('id="tbar-track"', self.index_html)
        self.assertIn('id="tbar-fill"', self.index_html)
        self.assertIn('id="tbar-slider"', self.index_html)
        self.assertIn('id="tbar-handle"', self.index_html)

    def test_app_js_tbar_event_listeners(self):
        """Verifica listeners de arrastre táctil y ratón en static/director/app.js."""
        self.assertIn("updateTbarUI", self.app_js)
        self.assertIn("commitTbar", self.app_js)
        self.assertIn("tbarTrack.addEventListener('mousedown'", self.app_js)
        self.assertIn("tbarTrack.addEventListener('touchstart'", self.app_js)
        self.assertIn("tbarTrack.addEventListener('touchmove'", self.app_js)
        self.assertIn("tbarTrack.addEventListener('touchend'", self.app_js)
        self.assertIn("isTbarEngaged", self.app_js)

    # =========================================================================
    # --- TAREA 2.4: MAPEO Y FEEDBACK DE TECLADO COMPLETO (HARDWARE KEYS) ---
    # =========================================================================
    def test_keyboard_shortcuts_coverage_angular(self):
        """Verifica la cobertura completa de atajos de teclado en Angular."""
        self.assertIn("e.key === '1'", self.director_ts)
        self.assertIn("e.shiftKey ? 'fade' : 'cut'", self.director_ts)
        self.assertIn("e.code === 'Space'", self.director_ts)
        self.assertIn("e.key === 'b' || e.key === 'B'", self.director_ts)
        self.assertIn("e.key === 'm' || e.key === 'M'", self.director_ts)
        self.assertIn("e.key === 'h' || e.key === 'H'", self.director_ts)
        self.assertIn("e.key === 't' || e.key === 'T'", self.director_ts)
        self.assertIn("e.key === 'g' || e.key === 'G'", self.director_ts)
        self.assertIn("e.key === 'r' || e.key === 'R'", self.director_ts)
        self.assertIn("e.ctrlKey", self.director_ts)

    def test_keyboard_keycap_active_signals_angular(self):
        """Verifica que Angular exponga activeKeys y el método isKeyActive."""
        self.assertIn("activeKeys = signal<Set<string>>", self.director_ts)
        self.assertIn("isKeyActive(key: string): boolean", self.director_ts)
        self.assertIn("handleKeyboardUp", self.director_ts)

    def test_keyboard_keycap_dom_bindings_angular(self):
        """Verifica que las keycaps de la UI tengan enlace reactivo a isKeyActive."""
        self.assertIn("isKeyActive('1')", self.director_html)
        self.assertIn("isKeyActive('2')", self.director_html)
        self.assertIn("isKeyActive('3')", self.director_html)
        self.assertIn("isKeyActive('b')", self.director_html)
        self.assertIn("isKeyActive(' ')", self.director_html)
        self.assertIn("isKeyActive('d')", self.director_html)
        self.assertIn("isKeyActive('r')", self.director_html)
        self.assertIn("isKeyActive('t')", self.director_html)

    def test_keyboard_shortcuts_coverage_static(self):
        """Verifica que app.js cubra todos los atajos de teclado y el feedback visual."""
        self.assertIn("KEYCAP_ELEMENTS", self.app_js)
        self.assertIn("triggerKeycapFeedback", self.app_js)
        self.assertIn("window.addEventListener('keydown'", self.app_js)
        self.assertIn("window.addEventListener('keyup'", self.app_js)

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print(" 🎬 INICIANDO VALIDACIÓN TÉCNICA RIGUROSA - SPRINT 2 (TAREAS 2.1, 2.2, 2.4)")
    print("=" * 80)
    unittest.main(verbosity=2)
