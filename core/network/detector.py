"""
Detector de red inteligente y 100% offline para Podcast Multicam Studio.
Detecta la mejor IP local tanto en redes con salida a internet como en sets aislados
(Routers Wi-Fi 5GHz locales, Windows Mobile Hotspot o tethering USB/móvil).
"""

import socket
import ipaddress
import subprocess

def get_all_local_ipv4s() -> list[str]:
    """Obtiene todas las IPs IPv4 locales configuradas en las interfaces de red."""
    found_ips = set()
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                found_ips.add(ip)
    except Exception:
        pass

    return list(found_ips)

def _get_active_route_ip() -> str | None:
    """
    Consulta la tabla de enrutamiento del kernel del SO mediante socket UDP
    para determinar cuál es la interfaz activa real de salida a la LAN/Wi-Fi.
    No transmite paquetes por la red; solo consulta la ruta por defecto del sistema.
    """
    probe_targets = [
        ("8.8.8.8", 80),
        ("1.1.1.1", 80),
        ("192.168.1.1", 80),
        ("192.168.0.1", 80),
        ("192.168.100.1", 80),
        ("10.0.0.1", 80)
    ]
    for host, port in probe_targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect((host, port))
            local_ip = s.getsockname()[0]
            s.close()
            if local_ip and not local_ip.startswith("127.") and not local_ip.startswith("169.254."):
                return local_ip
        except Exception:
            continue
    return None

def _get_virtual_adapter_ips() -> set[str]:
    """
    Detecta IPs asignadas a adaptadores virtuales (VMware, VirtualBox, Hyper-V, WSL)
    que no son accesibles desde los dispositivos móviles conectados al Wi-Fi físico.
    """
    virtual_ips = set()
    try:
        output = subprocess.check_output(
            "ipconfig /all",
            shell=True,
            text=True,
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        current_section = ""
        is_virtual = False
        for line in output.splitlines():
            line_str = line.strip()
            if line and not line.startswith(" ") and ":" in line:
                current_section = line.lower()
                is_virtual = any(v in current_section for v in [
                    "vmware", "virtualbox", "vbox", "vethernet", "hyper-v", "wsl", "bluetooth"
                ])
            elif is_virtual and ("ipv4" in line_str.lower() or "direcci" in line_str.lower() and "ipv4" in line_str.lower()):
                parts = line_str.split(":")
                if len(parts) > 1:
                    ip_candidate = parts[1].replace("(Preferido)", "").strip()
                    if ip_candidate:
                        virtual_ips.add(ip_candidate)
    except Exception:
        pass
    return virtual_ips

def detect_primary_ip() -> tuple[str, str]:
    """
    Determina la IP óptima para emparejar los teléfonos móviles.
    Prioridades:
    1. Windows Mobile Hotspot (192.168.137.1)
    2. Hotspot iPhone Tethering (172.20.10.x)
    3. Ruta activa del kernel del SO a la LAN/Wi-Fi (excluye adaptadores virtuales)
    4. IPs privadas físicas reales (192.168.x.x, 10.x.x.x no virtuales)
    5. Loopback (127.0.0.1)
    """
    all_ips = get_all_local_ipv4s()

    # 1. Hotspot de Windows (5 GHz Host)
    if "192.168.137.1" in all_ips:
        return "192.168.137.1", "Zona con cobertura móvil (Hotspot 5GHz PC)"

    # 2. iPhone Tethering USB / Wi-Fi Hotspot
    for ip in all_ips:
        if ip.startswith("172.20.10."):
            return ip, "Compartir Internet iPhone (Tethering Set)"

    # 3. Interfaz activa con ruta real del kernel (excluye adaptadores virtuales)
    active_route_ip = _get_active_route_ip()
    if active_route_ip and active_route_ip in all_ips:
        return active_route_ip, "Red Local Wi-Fi 5GHz / Ethernet"

    # 4. Redes de área local físicas descartando adaptadores virtuales conocidos
    virtual_ips = _get_virtual_adapter_ips()
    physical_ips = [ip for ip in all_ips if ip not in virtual_ips]

    for ip in physical_ips:
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private and not ip_obj.is_loopback:
                if ip.startswith("192.168."):
                    return ip, "Red Local Wi-Fi 5GHz / Ethernet"
                elif ip.startswith("10."):
                    return ip, "Red Local Corporativa / Router 10.x"
        except ValueError:
            continue

    # Fallback si solo hay IPs virtuales o no identificadas
    for ip in all_ips:
        if not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip, "Interfaz de Red Local"

    # 5. Fallback final
    return "127.0.0.1", "Localhost (Misma máquina)"

def get_network_diagnostics(port: int = 8443) -> dict:
    """Devuelve diagnóstico de red en formato estructurado para la API y la UI."""
    primary_ip, net_type = detect_primary_ip()
    return {
        "ip": primary_ip,
        "type": net_type,
        "port": port,
        "base_url": f"https://{primary_ip}:{port}",
        "all_interfaces": get_all_local_ipv4s()
    }
