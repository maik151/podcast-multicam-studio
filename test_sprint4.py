"""
Test Suite Riguroso - Sprint 4: Experiencia Móvil PWA & Ergonomía en Set
Tarea 4.1: Validación de Modo Ahorro Térmico (OLED Black Mode)
Tarea 4.2: Selector Óptico Multi-Lente (0.5x Ultra-Wide, 1x Main, 2x Tele)
Tarea 4.3: Control de Linterna de Apoyo (Fill Torch)
Tarea 4.4: Telemetría de Batería y Salud Térmica Periódica
"""

import unittest
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestSprint4MobileExperienceAndErgonomics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Rutas a archivos del frontend Angular
        cls.mobile_html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "mobile-cam", "mobile-cam.component.html"
        )
        cls.mobile_ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "mobile-cam", "mobile-cam.component.ts"
        )
        cls.director_html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.html"
        )
        cls.director_ts_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.ts"
        )
        cls.webrtc_service_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "services", "webrtc-signaling.service.ts"
        )
        cls.models_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "core", "models", "studio.models.ts"
        )

        # Rutas a archivos estáticos PWA
        cls.static_mobile_html_path = os.path.join(BASE_DIR, "static", "mobile", "index.html")
        cls.static_mobile_js_path = os.path.join(BASE_DIR, "static", "mobile", "app.js")
        cls.static_director_html_path = os.path.join(BASE_DIR, "static", "director", "index.html")
        cls.static_director_js_path = os.path.join(BASE_DIR, "static", "director", "app.js")

        # Backend Hub
        cls.signaling_hub_path = os.path.join(BASE_DIR, "core", "signaling", "hub.py")

        with open(cls.mobile_html_path, "r", encoding="utf-8") as f:
            cls.mobile_html = f.read()
        with open(cls.mobile_ts_path, "r", encoding="utf-8") as f:
            cls.mobile_ts = f.read()
        with open(cls.director_html_path, "r", encoding="utf-8") as f:
            cls.director_html = f.read()
        with open(cls.director_ts_path, "r", encoding="utf-8") as f:
            cls.director_ts = f.read()
        with open(cls.webrtc_service_path, "r", encoding="utf-8") as f:
            cls.webrtc_ts = f.read()
        with open(cls.models_path, "r", encoding="utf-8") as f:
            cls.models_ts = f.read()
        with open(cls.static_mobile_html_path, "r", encoding="utf-8") as f:
            cls.static_mobile_html = f.read()
        with open(cls.static_mobile_js_path, "r", encoding="utf-8") as f:
            cls.static_mobile_js = f.read()
        with open(cls.static_director_html_path, "r", encoding="utf-8") as f:
            cls.static_director_html = f.read()
        with open(cls.static_director_js_path, "r", encoding="utf-8") as f:
            cls.static_director_js = f.read()
        with open(cls.signaling_hub_path, "r", encoding="utf-8") as f:
            cls.hub_py = f.read()

    # =========================================================================
    # 1. PRUEBAS DE VISTA OLED EN ANGULAR (mobile-cam.component.html)
    # =========================================================================

    def test_01_angular_mobile_cam_has_oled_overlay_element(self):
        """Verifica que el componente móvil de Angular defina el contenedor #oled-view."""
        self.assertIn('id="oled-view"', self.mobile_html, "Falta el id #oled-view en el template móvil.")
        self.assertIn('*ngIf="isOledActive()"', self.mobile_html, "El contenedor OLED debe ligarse reactivamente a isOledActive().")

    def test_02_angular_mobile_cam_pure_black_oled_background(self):
        """Verifica que el modo OLED utilice negro absoluto (#000000) para apagar subpíxeles."""
        self.assertIn('bg-[#000000]', self.mobile_html, "El modo OLED debe emplear negro puro #000000.")
        self.assertTrue('&lt; 0.25W' in self.mobile_html or '< 0.25W' in self.mobile_html,
                        "Debe reportar consumo mínimo estimado < 0.25W.")

    def test_03_angular_mobile_cam_tally_perimeter_borders(self):
        """Verifica que el marco perimetral Tally en modo OLED refleje ON AIR y PREVIEW."""
        self.assertIn('#ff3b30', self.mobile_html, "Falta el color Tally rojo de Program en el borde OLED.")
        self.assertIn('#ffb68b', self.mobile_html, "Falta el color Tally suave para Preview en el borde OLED.")

    def test_04_angular_mobile_cam_tap_to_restore_handler(self):
        """Verifica que tocar la pantalla OLED invoque exitOledSaver() para regresar inmediatamente."""
        self.assertIn('(click)="exitOledSaver()"', self.mobile_html, "Debe tener manejador de click para restaurar la vista.")

    def test_05_angular_mobile_cam_has_oled_toggle_button(self):
        """Verifica que la barra superior móvil cuente con el botón #btn-oled para entrar a modo ahorro."""
        self.assertIn('id="btn-oled"', self.mobile_html, "Falta el botón físico/táctil #btn-oled.")
        self.assertIn('(click)="toggleOled()"', self.mobile_html, "El botón #btn-oled debe invocar toggleOled().")

    # =========================================================================
    # 2. PRUEBAS DE LÓGICA Y REACTIVIDAD EN ANGULAR (mobile-cam.component.ts)
    # =========================================================================

    def test_06_angular_mobile_cam_signal_and_methods(self):
        """Verifica que el componente declare la signal isOledActive y los métodos de control."""
        self.assertIn('public isOledActive = signal<boolean>(false)', self.mobile_ts, "Falta la signal isOledActive.")
        self.assertIn('public toggleOled(): void', self.mobile_ts, "Falta la firma del método toggleOled().")
        self.assertIn('public exitOledSaver(): void', self.mobile_ts, "Falta la firma del método exitOledSaver().")

    def test_07_angular_mobile_cam_stream_persistence_in_oled(self):
        """Verifica que el modo OLED no detenga el MediaStream ni cancele la transmisión WebRTC."""
        self.assertNotIn('localStream.getTracks().forEach', self.mobile_ts.split('toggleOled')[1].split('exitOledSaver')[0],
                         "El método toggleOled NO debe detener los tracks de cámara.")

    def test_08_angular_mobile_cam_remote_websocket_command_listener(self):
        """Verifica que la cámara móvil atienda el comando remoto toggle_oled emitido por el director."""
        self.assertTrue('toggle_oled' in self.mobile_ts, "Debe procesar la acción remota toggle_oled.")
        self.assertTrue('toggleOled()' in self.mobile_ts, "Debe invocar toggleOled() ante la orden remota.")

    # =========================================================================
    # 3. CONTROL REMOTO DESDE LA CONSOLA DEL DIRECTOR (Angular)
    # =========================================================================

    def test_09_director_webrtc_service_has_camera_command(self):
        """Verifica que WebRtcSignalingService disponga de sendCameraCommand para enviar órdenes a móviles."""
        self.assertIn('sendCameraCommand(camId:', self.webrtc_ts, "Falta sendCameraCommand en WebRtcSignalingService.")
        self.assertIn("type: 'camera_command'", self.webrtc_ts, "sendCameraCommand debe despachar mensajes camera_command.")

    def test_10_director_component_has_remote_oled_toggle(self):
        """Verifica que DirectorComponent exponga toggleRemoteOled(camId)."""
        self.assertIn('public toggleRemoteOled(camId: number): void', self.director_ts, "Falta toggleRemoteOled en DirectorComponent.")
        self.assertIn('toggleRemoteOled(cam.id)', self.director_html, "La UI del director debe tener botón remoto para conmutar OLED.")

    # =========================================================================
    # 4. PARIDAD CON PWA MÓVIL ESTÁTICA (static/mobile/index.html & app.js)
    # =========================================================================

    def test_11_static_mobile_oled_html_elements(self):
        """Verifica que el index.html móvil estático posea #oled-view y botón #btn-oled."""
        self.assertIn('id="oled-view"', self.static_mobile_html, "Falta #oled-view en static/mobile/index.html.")
        self.assertIn('id="btn-oled"', self.static_mobile_html, "Falta #btn-oled en static/mobile/index.html.")
        self.assertIn('id="oled-battery-val"', self.static_mobile_html, "Falta telemetría de batería en oled-view estático.")

    def test_12_static_mobile_oled_js_toggle_and_remote(self):
        """Verifica que app.js móvil implemente toggleOled(), exitOledSaver() y soporte el comando remoto."""
        self.assertIn('function toggleOled()', self.static_mobile_js, "Falta toggleOled en static/mobile/app.js.")
        self.assertIn('function exitOledSaver()', self.static_mobile_js, "Falta exitOledSaver en static/mobile/app.js.")
        self.assertIn("toggle_oled", self.static_mobile_js, "Falta manejo del comando toggle_oled en static/mobile/app.js.")

    # =========================================================================
    # 5. ENRUTAMIENTO EN BACKEND SIGNALING HUB (core/signaling/hub.py)
    # =========================================================================

    def test_13_signaling_hub_routes_camera_commands(self):
        """Verifica que el hub de señalización aiohttp distribuya camera_command al teléfono correspondiente."""
        self.assertIn('msg_type == "camera_command"', self.hub_py, "El Hub de señalización debe enrutar camera_command.")
        self.assertIn('target_cam = str(data.get("camId"))', self.hub_py, "El Hub debe identificar el camId de destino.")

    # =========================================================================
    # 6. TAREA 4.2: SELECTOR ÓPTICO MULTI-LENTE (0.5x Ultra-Wide, 1x Main, 2x Tele)
    # =========================================================================

    def test_14_angular_mobile_cam_has_zoom_buttons_in_html(self):
        """Verifica que el template móvil de Angular contenga los botones de lentes 0.5x, 1x y 2x."""
        self.assertIn('btn-zoom-', self.mobile_html, "Faltan los selectores de zoom en mobile-cam.component.html.")
        self.assertIn('(click)="setZoom(z)"', self.mobile_html, "Los botones de lente deben invocar setZoom(z).")

    def test_15_angular_mobile_cam_zoom_signals_and_methods(self):
        """Verifica que MobileCamComponent implemente signals y métodos de zoom óptico sin reiniciar WebRTC."""
        self.assertIn('public currentZoom = signal<number>(1.0)', self.mobile_ts, "Falta la signal currentZoom.")
        self.assertIn('public availableZooms = signal<number[]>([0.5, 1.0, 2.0])', self.mobile_ts, "Falta availableZooms.")
        self.assertIn('public async setZoom(factor: number): Promise<void>', self.mobile_ts, "Falta el método setZoom.")
        self.assertIn('public async cycleLens(): Promise<void>', self.mobile_ts, "Falta el método cycleLens.")
        self.assertIn('track.applyConstraints', self.mobile_ts, "Debe aplicar constraints al track sin reiniciar WebRTC.")
        self.assertIn('zoom: target', self.mobile_ts, "Debe pasar la constraint de zoom al track.")

    def test_16_angular_mobile_cam_remote_zoom_commands(self):
        """Verifica que MobileCamComponent procese órdenes remotas set_zoom y switch_lens."""
        self.assertIn('set_zoom', self.mobile_ts, "Debe procesar el comando remoto set_zoom.")
        self.assertIn('switch_lens', self.mobile_ts, "Debe procesar el comando remoto switch_lens.")

    def test_17_director_lens_controls_angular(self):
        """Verifica que DirectorComponent y su template tengan botones de control remoto de lentes."""
        self.assertIn('setRemoteLens(camId: number, zoom: number)', self.director_ts, "Falta setRemoteLens en DirectorComponent.")
        self.assertIn('cycleRemoteLens(camId: number)', self.director_ts, "Falta cycleRemoteLens en DirectorComponent.")
        self.assertIn('setCameraZoom', self.webrtc_ts, "Falta setCameraZoom en WebRtcSignalingService.")
        self.assertIn('btn-remote-lens-05-', self.director_html, "Falta botón 0.5x en la UI del Director.")
        self.assertIn('btn-remote-lens-10-', self.director_html, "Falta botón 1.0x en la UI del Director.")
        self.assertIn('btn-remote-lens-20-', self.director_html, "Falta botón 2.0x en la UI del Director.")

    def test_18_static_pwa_optical_zoom_parity(self):
        """Verifica la paridad de multi-lente en la PWA estática (index.html, app.js móvil y app.js director)."""
        self.assertIn('id="lens-05"', self.static_mobile_html, "Falta selector lens-05 en static/mobile/index.html.")
        self.assertIn('id="lens-10"', self.static_mobile_html, "Falta selector lens-10 en static/mobile/index.html.")
        self.assertIn('id="lens-20"', self.static_mobile_html, "Falta selector lens-20 en static/mobile/index.html.")
        self.assertIn('function setLens(lensId)', self.static_mobile_js, "Falta setLens en static/mobile/app.js.")
        self.assertIn('function cycleLens()', self.static_mobile_js, "Falta cycleLens en static/mobile/app.js.")
        self.assertIn("set_zoom", self.static_mobile_js, "Falta soporte para set_zoom en static/mobile/app.js.")
        self.assertIn('function sendCameraZoom', self.static_director_js, "Falta sendCameraZoom en static/director/app.js.")

    # =========================================================================
    # 7. TAREA 4.3: CONTROL DE LINTERNA DE APOYO (Fill Torch)
    # =========================================================================

    def test_19_angular_mobile_cam_has_torch_button(self):
        """Verifica que mobile-cam.component.html contenga el botón #btn-torch con icono reactivo."""
        self.assertIn('id="btn-torch"', self.mobile_html, "Falta el id #btn-torch en el template móvil.")
        self.assertIn('(click)="toggleTorch()"', self.mobile_html, "El botón #btn-torch debe invocar toggleTorch().")
        self.assertIn('flashlight_on', self.mobile_html, "Debe tener icono de linterna encendida.")
        self.assertIn('flashlight_off', self.mobile_html, "Debe tener icono de linterna apagada.")

    def test_20_angular_mobile_cam_torch_signal_and_constraints(self):
        """Verifica que MobileCamComponent controle la linterna continua mediante applyConstraints."""
        self.assertIn('public isTorchOn = signal<boolean>(false)', self.mobile_ts, "Falta la signal isTorchOn.")
        self.assertIn('public async toggleTorch(): Promise<void>', self.mobile_ts, "Falta el método toggleTorch.")
        self.assertIn('torch: next', self.mobile_ts, "toggleTorch debe aplicar la constraint de torch.")

    def test_21_angular_mobile_cam_remote_torch_command(self):
        """Verifica que MobileCamComponent procese la orden remota toggle_torch."""
        self.assertIn('toggle_torch', self.mobile_ts, "Debe procesar la acción remota toggle_torch.")

    def test_22_director_remote_torch_angular(self):
        """Verifica que DirectorComponent y su UI dispongan del botón ⚡ FLASH remoto para cada cámara."""
        self.assertIn('toggleRemoteTorch(camId: number)', self.director_ts, "Falta toggleRemoteTorch en DirectorComponent.")
        self.assertIn('toggleCameraTorch', self.webrtc_ts, "Falta toggleCameraTorch en WebRtcSignalingService.")
        self.assertIn('btn-remote-torch-', self.director_html, "Faltan los botones btn-remote-torch- en la UI del Director.")
        self.assertIn('FLASH', self.director_html, "Debe incluir etiqueta FLASH en la barra de control remoto.")

    def test_23_static_torch_parity(self):
        """Verifica la paridad de la linterna en la PWA estática y el panel de director."""
        self.assertIn('async function toggleTorch()', self.static_mobile_js, "Falta toggleTorch en static/mobile/app.js.")
        self.assertIn('toggle_torch', self.static_director_html, "Falta botón toggle_torch en static/director/index.html.")

    # =========================================================================
    # 8. TAREA 4.4: TELEMETRÍA DE BATERÍA Y SALUD TÉRMICA PERIÓDICA (CADA 5S)
    # =========================================================================

    def test_24_angular_mobile_cam_battery_periodic_interval(self):
        """Verifica que mobile-cam.component.ts configure el intervalo periódico cada 5000ms."""
        self.assertIn('window.setInterval', self.mobile_ts, "Debe configurar intervalo de telemetría periódica.")
        self.assertIn('5000', self.mobile_ts, "El intervalo de reporte debe estar calibrado a 5000 ms (5 segundos).")
        self.assertIn('clearInterval(this.batteryInterval)', self.mobile_ts, "Debe limpiar el intervalo en ngOnDestroy.")

    def test_25_angular_mobile_cam_reports_battery_and_thermal_payload(self):
        """Verifica que reportBattery despache telemetría con nivel, carga y salud térmica."""
        self.assertIn('public reportBattery(): void', self.mobile_ts, "Falta el método público reportBattery.")
        self.assertIn('thermalStatus', self.mobile_ts, "El reporte debe incluir la salud térmica calculada.")
        self.assertIn('COOLED', self.mobile_ts, "Debe reportar estado COOLED cuando OLED saver está activo.")

    def test_26_webrtc_service_updates_camera_battery_and_thermal(self):
        """Verifica que WebRtcSignalingService actualice batteryLevel, isCharging y thermalStatus."""
        self.assertIn('thermalStatus', self.webrtc_ts, "WebRtcSignalingService debe guardar thermalStatus.")
        self.assertIn('batteryLevel: level', self.webrtc_ts, "Debe actualizar batteryLevel en el estado de la cámara.")
        self.assertIn('thermalStatus?: string;', self.models_ts, "CameraFeed model debe contener el campo thermalStatus.")

    def test_27_director_ui_displays_battery_and_charging_icons(self):
        """Verifica que director.component.html muestre el porcentaje de batería e iconos técnicos."""
        self.assertIn('bat-cam-', self.director_html, "Falta el identificador bat-cam- en las tarjetas de cámara del director.")
        self.assertTrue('bolt' in self.director_html or '⚡' in self.director_html, "Debe mostrar icono bolt cuando el teléfono está cargando.")
        self.assertTrue('battery_std' in self.director_html or '🔋' in self.director_html, "Debe mostrar icono battery_std cuando el teléfono está en batería.")
        self.assertIn('thermalStatus', self.director_html, "La UI del director debe mostrar el badge de salud térmica.")

    def test_28_static_telemetry_5s_interval_and_director_parity(self):
        """Verifica la paridad de telemetría de 5 segundos en static/mobile/app.js y static/director/app.js."""
        self.assertIn('5000', self.static_mobile_js, "static/mobile/app.js debe tener intervalo de 5000ms.")
        self.assertIn('bat-cam-', self.static_director_js, "static/director/app.js debe actualizar los elementos bat-cam-.")
        self.assertIn('msg_type in ("telemetry", "battery", "camera_telemetry")', self.hub_py,
                      "El Hub de señalización debe enrutar todos los tipos de telemetría.")

if __name__ == '__main__':
    unittest.main()
