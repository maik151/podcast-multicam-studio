"""
Detector de red y adaptadores para Podcast Multicam Studio.
Detecta la mejor IP local tanto en redes con salida a internet como en sets aislados
(Routers Wi-Fi 5GHz locales, Windows Mobile Hotspot o tethering USB/móvil).
"""

from core.network.detector import detect_primary_ip, get_all_local_ipv4s, get_network_diagnostics

if __name__ == "__main__":
    diag = get_network_diagnostics()
    print(f"Red seleccionada: {diag['type']}")
    print(f"URL de conexión: {diag['base_url']}")
