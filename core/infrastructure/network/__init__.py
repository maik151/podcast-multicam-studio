"""
Adaptadores de Red e Infraestructura.
"""

from core.network.detector import detect_primary_ip, get_all_local_ipv4s, get_network_diagnostics
from core.network.port_manager import is_port_in_use, release_port_if_busy
from core.network.ssl_manager import generate_ssl_certificate, create_ssl_context
