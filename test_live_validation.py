"""
Validación de Entrega de Assets de Marca, Identidad Visual y Rutas del Servidor.
"""

import unittest
import os
from aiohttp import web
from core.presentation.app_factory import create_application, ApplicationContainer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestBrandAssetsAndDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = ApplicationContainer()
        cls.app = create_application(cls.container)
        cls.routes = [r.resource.canonical for r in cls.app.router.routes() if hasattr(r, 'resource') and r.resource]
        cls.dist_dir = os.path.join(BASE_DIR, "frontend", "dist", "frontend", "browser")
        cls.public_dir = os.path.join(BASE_DIR, "frontend", "public")
        cls.static_assets_dir = os.path.join(BASE_DIR, "static", "assets")

    def test_01_public_brand_assets_exist(self):
        """Verifica que todos los archivos oficiales .svg y .png de la marca existan en public/."""
        required = [
            "tx_studio_logoNaranja.svg",
            "tx_studio_logoNaranja.png",
            "tx_studio_Isotipo_naranja.svg",
            "tx_studio_Isotipo_naranja.png",
            "tx_studio_logoBlanco.svg",
            "tx_studio_logoBlanco.png",
            "tx_studio_Isotipo_blanco.svg",
            "tx_studio_Isotipo_blanco.png",
            "tx_studio_logoGris.svg",
            "tx_studio_logoGris.png",
            "tx_studio_Isotipo_gris.svg",
            "tx_studio_Isotipo_gris.png"
        ]
        for f in required:
            path = os.path.join(self.public_dir, f)
            self.assertTrue(os.path.exists(path), f"Falta el archivo de marca {f} en frontend/public/")

    def test_02_compiled_dist_brand_assets_exist(self):
        """Verifica que los assets de marca se hayan copiado a dist/frontend/browser tras el build."""
        self.assertTrue(os.path.exists(os.path.join(self.dist_dir, "tx_studio_logoNaranja.svg")),
                        "Falta tx_studio_logoNaranja.svg en dist/")
        self.assertTrue(os.path.exists(os.path.join(self.dist_dir, "tx_studio_Isotipo_naranja.svg")),
                        "Falta tx_studio_Isotipo_naranja.svg en dist/")

    def test_03_app_router_serves_brand_assets(self):
        """Verifica que el router registre los endpoints para los assets de marca en la raíz."""
        self.assertIn("/tx_studio_logoNaranja.svg", self.routes, "La ruta /tx_studio_logoNaranja.svg debe estar en el router.")
        self.assertIn("/tx_studio_Isotipo_naranja.svg", self.routes, "La ruta /tx_studio_Isotipo_naranja.svg debe estar en el router.")

    def test_04_director_header_embeds_logo_naranja_svg(self):
        """Verifica que la consola del Director integre el logo/isotipo vectorial oficial de TX-Studio."""
        director_html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "director", "director.component.html"
        )
        with open(director_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        has_brand_mark = ("tx_studio_Isotipo_naranja.svg" in html) or ("tx_studio_logoNaranja.svg" in html)
        self.assertTrue(has_brand_mark, "director.component.html debe utilizar tx_studio_Isotipo_naranja.svg o tx_studio_logoNaranja.svg")
        self.assertIn("tx_studio_Isotipo_naranja.svg", html, "director.component.html debe incluir el isotipo.")

    def test_05_mobile_cam_embeds_brand_isotipo(self):
        """Verifica que la cámara móvil incorpore el isotipo de la marca en la barra y en modo OLED."""
        mobile_html_path = os.path.join(
            BASE_DIR, "frontend", "src", "app", "features", "mobile-cam", "mobile-cam.component.html"
        )
        with open(mobile_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("tx_studio_Isotipo_naranja.svg", html, "mobile-cam.component.html debe incluir el isotipo naranja.")
        self.assertIn("tx_studio_Isotipo_gris.svg", html, "mobile-cam.component.html debe incluir el isotipo gris en OLED.")

    def test_06_index_html_has_brand_favicons(self):
        """Verifica que index.html enlace los favicons vectoriales y PNG adaptados a la marca."""
        index_html_path = os.path.join(BASE_DIR, "frontend", "src", "index.html")
        with open(index_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('href="tx_studio_Isotipo_naranja.svg"', html, "index.html debe tener favicon SVG tx_studio_Isotipo_naranja.svg")
        self.assertIn('href="tx_studio_Isotipo_naranja.png"', html, "index.html debe tener favicon PNG tx_studio_Isotipo_naranja.png")

if __name__ == '__main__':
    unittest.main()
