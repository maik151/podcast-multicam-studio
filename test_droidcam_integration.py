"""
Pruebas unitarias para el motor USB DroidCam (Android ADB & Apple usbmuxd) y sus endpoints REST.
"""

import unittest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from core.network.droidcam_bridge import DroidCamBridgeManager, DROIDCAM_CAMERA_PORTS
from core.presentation.app_factory import create_application, ApplicationContainer


class TestDroidCamBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = DroidCamBridgeManager()

    def test_ports_mapping_strict_3_cameras(self):
        """Verifica que el mapeo de puertos corresponda exactamente a las 3 cámaras."""
        self.assertEqual(self.bridge.camera_ports[1], 4741)
        self.assertEqual(self.bridge.camera_ports[2], 4742)
        self.assertEqual(self.bridge.camera_ports[3], 4743)
        self.assertEqual(len(self.bridge.camera_ports), 3)

    def test_scan_devices_structure(self):
        """Verifica que el escaneo de dispositivos devuelva la estructura correcta."""
        scan = self.bridge.scan_devices()
        self.assertIn("devices", scan)
        self.assertIn("android_count", scan)
        self.assertIn("ios_count", scan)
        self.assertIn("active_bindings", scan)
        self.assertIsInstance(scan["devices"], list)

    def test_bind_invalid_camera_id(self):
        """Verifica que rechace IDs de cámara fuera del rango 1..3."""
        res = self.bridge.bind_camera(cam_id=4, device_id="dummy", platform="android")
        self.assertFalse(res["success"])
        self.assertIn("inválida", res["message"])

    def test_bind_invalid_platform(self):
        """Verifica que rechace plataformas desconocidas."""
        res = self.bridge.bind_camera(cam_id=1, device_id="dummy", platform="windows_phone")
        self.assertFalse(res["success"])
        self.assertIn("no soportada", res["message"])

    def test_unbind_camera(self):
        """Verifica que unbind_camera funcione limpiamente."""
        res = self.bridge.unbind_camera(1)
        self.assertTrue(res["success"])
        summary = self.bridge.get_bindings_summary()
        self.assertFalse(summary[1]["bound"])


class TestDroidCamApi(AioHTTPTestCase):
    async def get_application(self):
        container = ApplicationContainer()
        return create_application(container)

    @unittest_run_loop
    async def test_get_devices_endpoint(self):
        """Prueba endpoint GET /api/droidcam/devices."""
        resp = await self.client.request("GET", "/api/droidcam/devices")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("devices", data)
        self.assertIn("android_count", data)
        self.assertIn("ios_count", data)

    @unittest_run_loop
    async def test_get_status_endpoint(self):
        """Prueba endpoint GET /api/droidcam/status."""
        resp = await self.client.request("GET", "/api/droidcam/status")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("1", data)
        self.assertIn("2", data)
        self.assertIn("3", data)
        self.assertEqual(data["1"]["port"], 4741)

    @unittest_run_loop
    async def test_bind_endpoint_no_devices(self):
        """Prueba endpoint POST /api/droidcam/bind sin dispositivo disponible."""
        with unittest.mock.patch.object(self.app["container"].droidcam_controller.bridge, "scan_devices", return_value={"devices": []}):
            payload = {"cam_id": 1, "platform": "android", "device_id": ""}
            resp = await self.client.request("POST", "/api/droidcam/bind", json=payload)
            self.assertEqual(resp.status, 400)
            data = await resp.json()
            self.assertFalse(data["success"])

    @unittest_run_loop
    async def test_unbind_endpoint(self):
        """Prueba endpoint POST /api/droidcam/unbind."""
        payload = {"cam_id": 2}
        resp = await self.client.request("POST", "/api/droidcam/unbind", json=payload)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(data["success"])


if __name__ == "__main__":
    unittest.main()
