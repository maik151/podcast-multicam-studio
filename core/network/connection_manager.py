"""
Gestor de Conexiones Multiruta y Hub USB para Podcast Multicam Studio.
Gestiona de forma inteligente y 100% offline:
1. Hub USB Físico con Android ADB (reversión de puertos tcp:8443 -> localhost).
2. Conexiones USB Tethering (Apple Mobile Device iOS 172.20.10.x y Android RNDIS 192.168.42.x).
3. Hotspot Wi-Fi 5 GHz de Windows (192.168.137.1) con detección de estado dinámico.
4. Redes Wi-Fi / Ethernet LAN locales.
5. Optimización de enrutamiento mixto para CERO pérdida de paquetes y máxima estabilidad.
"""

import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional


def find_adb_executable() -> Optional[str]:
    """Busca el ejecutable de ADB en las herramientas locales de TX-Studio, en PATH o en ubicaciones de Android SDK."""
    try:
        from core.config import BASE_DIR, BUNDLE_DIR
        for b_path in (BUNDLE_DIR, BASE_DIR):
            bundled_adb = os.path.join(b_path, "tools", "platform-tools", "adb.exe")
            if os.path.isfile(bundled_adb):
                return bundled_adb
    except Exception:
        pass

    adb_path = shutil.which("adb")
    if adb_path:
        return adb_path

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
        r"C:\Program Files\Android\platform-tools\adb.exe"
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def detect_connected_mtp_devices() -> List[Dict[str, Any]]:
    """Detecta teléfonos móviles conectados por cable USB en modo MTP/Almacenamiento masivo que aún no tienen ADB activo."""
    mtp_devices = []
    try:
        import winreg
        usb_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB")
        for i in range(winreg.QueryInfoKey(usb_key)[0]):
            vid_pid = winreg.EnumKey(usb_key, i)
            try:
                device_key = winreg.OpenKey(usb_key, vid_pid)
                for j in range(winreg.QueryInfoKey(device_key)[0]):
                    inst = winreg.EnumKey(device_key, j)
                    inst_key = winreg.OpenKey(device_key, inst)
                    try:
                        service, _ = winreg.QueryValueEx(inst_key, "Service")
                        desc, _ = winreg.QueryValueEx(inst_key, "DeviceDesc")
                        if "mtp" in service.lower() or "wpd" in service.lower():
                            # Limpiar nombre comercial
                            clean_name = desc.split(";")[-1] if ";" in desc else desc
                            mtp_devices.append({"id": inst, "service": service, "name": clean_name})
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return mtp_devices


def get_adb_devices(port: int = 8443) -> Dict[str, Any]:
    """
    Escanea dispositivos Android conectados por cable USB mediante ADB.
    Verifica también si el túnel inverso 'reverse tcp:{port} tcp:{port}' está activo.
    """
    adb_bin = find_adb_executable()
    if not adb_bin:
        return {
            "available": False,
            "adb_path": None,
            "devices": [],
            "message": "ADB no encontrado en PATH ni en Android SDK."
        }

    devices: List[Dict[str, Any]] = []
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output = subprocess.check_output(
            [adb_bin, "devices", "-l"],
            text=True,
            errors="ignore",
            timeout=3,
            creationflags=flags
        )

        for line in output.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("List of devices") or line_str.startswith("*"):
                continue

            parts = line_str.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]

                model = "Android Device"
                model_match = re.search(r"model:(\S+)", line_str)
                if model_match:
                    model = model_match.group(1).replace("_", " ")

                product_match = re.search(r"product:(\S+)", line_str)
                product = product_match.group(1) if product_match else ""

                # Comprobar si tiene el túnel reverso activo
                is_reversed = False
                try:
                    rev_out = subprocess.check_output(
                        [adb_bin, "-s", serial, "reverse", "--list"],
                        text=True,
                        errors="ignore",
                        timeout=2,
                        creationflags=flags
                    )
                    if f"tcp:{port}" in rev_out:
                        is_reversed = True
                except Exception:
                    pass

                devices.append({
                    "serial": serial,
                    "state": state,
                    "model": model,
                    "product": product,
                    "reversed": is_reversed,
                    "direct_url": f"https://localhost:{port}"
                })

        pending_mtp = None
        if not devices:
            mtp_candidates = detect_connected_mtp_devices()
            if mtp_candidates:
                pending_mtp = mtp_candidates[0]

        has_active_tunnel = any(d.get("reversed", False) for d in devices)

        return {
            "available": True,
            "adb_path": adb_bin,
            "devices": devices,
            "count": len(devices),
            "pending_mtp": pending_mtp,
            "has_active_tunnel": has_active_tunnel,
            "message": f"{len(devices)} dispositivo(s) detectado(s) vía cable USB ADB."
        }
    except Exception as exc:
        return {
            "available": True,
            "adb_path": adb_bin,
            "devices": [],
            "error": str(exc),
            "message": f"Error ejecutando ADB: {exc}"
        }


def reverse_all_adb_devices(port: int = 8443) -> Dict[str, Any]:
    """
    Aplica 'adb reverse tcp:{port} tcp:{port}' a todos los dispositivos conectados por USB.
    Permite a los móviles acceder a la consola como https://localhost:{port}/cam/X por cable directo.
    """
    adb_bin = find_adb_executable()
    if not adb_bin:
        return {"success": False, "reversed_count": 0, "message": "ADB no disponible."}

    scan = get_adb_devices(port)
    devices = scan.get("devices", [])
    if not devices:
        return {"success": False, "reversed_count": 0, "message": "No hay dispositivos USB ADB conectados."}

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    success_count = 0
    results = []

    for dev in devices:
        serial = dev["serial"]
        try:
            cmd = [adb_bin, "-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"]
            subprocess.check_call(cmd, timeout=3, creationflags=flags)
            success_count += 1
            results.append({"serial": serial, "status": "ok", "url": f"https://localhost:{port}"})
        except Exception as e:
            results.append({"serial": serial, "status": "error", "error": str(e)})

    return {
        "success": success_count > 0,
        "reversed_count": success_count,
        "total_devices": len(devices),
        "results": results,
        "message": f"Túnel USB revertido en {success_count}/{len(devices)} dispositivos (puerto {port})."
    }


def parse_network_adapters() -> List[Dict[str, Any]]:
    """
    Parsea las interfaces de red de Windows mediante 'ipconfig /all'.
    Retorna nombre, descripción, estado de desconexión y dirección IPv4.
    """
    adapters: List[Dict[str, Any]] = []
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output = subprocess.check_output(
            "ipconfig /all",
            shell=True,
            text=True,
            errors="ignore",
            timeout=4,
            creationflags=flags
        )

        current: Optional[Dict[str, Any]] = None
        for line in output.splitlines():
            if line and not line.startswith(" ") and line.endswith(":"):
                header = line.rstrip(":").strip()
                if "adaptador" in header.lower() or "adapter" in header.lower():
                    current = {"name": header, "desc": "", "ip": None, "disconnected": False}
                    adapters.append(current)
                else:
                    current = None
            elif current is not None:
                sline = line.strip()
                if "descripci" in sline.lower() or "description" in sline.lower():
                    parts = sline.split(":", 1)
                    if len(parts) > 1:
                        current["desc"] = parts[1].strip()
                elif "desconectados" in sline.lower() or "disconnected" in sline.lower():
                    current["disconnected"] = True
                elif "ipv4" in sline.lower() or ("direcci" in sline.lower() and "ipv4" in sline.lower()):
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", sline)
                    if match:
                        current["ip"] = match.group(1)
    except Exception:
        pass

    return adapters


def open_windows_hotspot_settings() -> bool:
    """Abre la ventana de configuración del Hotspot Móvil en Windows 10/11."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd", "/c", "start", "ms-settings:network-mobilehotspot"],
            shell=False,
            creationflags=flags
        )
        return True
    except Exception:
        return False


def get_full_connection_matrix(port: int = 8443) -> Dict[str, Any]:
    """
    Compila la matriz completa de conexiones físicas, USB y Wi-Fi con diagnósticos y rutas de enlace.
    """
    adapters = parse_network_adapters()

    hotspot_info = {
        "active": False,
        "ip": None,
        "name": "Zona con Cobertura Móvil (Windows Hotspot 5 GHz)",
        "adapter_desc": None,
        "suggested_band": "5 GHz"
    }

    apple_usb_info = {
        "active": False,
        "ip": None,
        "name": "Apple Mobile Device Ethernet (iOS USB Tethering)",
        "adapter_desc": None
    }

    android_rndis_info = {
        "active": False,
        "ip": None,
        "name": "Android USB Tethering (RNDIS)",
        "adapter_desc": None
    }

    wifi_lan_info = {
        "active": False,
        "ip": None,
        "name": "Red Local Wi-Fi / LAN",
        "adapter_desc": None
    }

    all_active_ips: List[str] = []

    for a in adapters:
        ip = a.get("ip")
        if not ip or a.get("disconnected"):
            continue

        desc = a.get("desc", "").lower()
        name = a.get("name", "").lower()

        # Filtrar hipervisores y redes virtuales no accesibles por móviles
        if any(v in desc or v in name for v in ["vmware", "virtualbox", "vethernet", "hyper-v", "wsl", "bluetooth"]):
            continue

        all_active_ips.append(ip)

        # 1. Hotspot de Windows (192.168.137.1 o Wi-Fi Direct activo)
        if ip == "192.168.137.1" or "wi-fi direct" in desc:
            hotspot_info["active"] = True
            hotspot_info["ip"] = ip
            hotspot_info["adapter_desc"] = a.get("desc")

        # 2. iPhone USB Tethering
        elif "apple" in desc or "apple" in name or ip.startswith("172.20.10."):
            apple_usb_info["active"] = True
            apple_usb_info["ip"] = ip
            apple_usb_info["adapter_desc"] = a.get("desc")

        # 3. Android USB Tethering (RNDIS)
        elif ("ndis" in desc or "remote ndis" in desc) or ip.startswith("192.168.42."):
            android_rndis_info["active"] = True
            android_rndis_info["ip"] = ip
            android_rndis_info["adapter_desc"] = a.get("desc")

        # 4. Wi-Fi / Ethernet Físico
        elif any(w in desc or w in name for w in ["wi-fi", "wireless", "802.11", "ethernet", "realtek", "intel"]):
            if not wifi_lan_info["active"]:
                wifi_lan_info["active"] = True
                wifi_lan_info["ip"] = ip
                wifi_lan_info["adapter_desc"] = a.get("desc")

    # ADB Devices
    adb_data = get_adb_devices(port)

    # Catálogo de rutas de conexión disponibles para las cámaras
    available_routes: List[Dict[str, Any]] = []

    # Opción 1: Hub USB Cable (Localhost)
    available_routes.append({
        "id": "usb_hub_adb",
        "title": "Hub USB Cable (Android ADB)",
        "badge": "0ms LATENCIA // CABLE FÍSICO",
        "ip": "localhost",
        "base_url": f"https://localhost:{port}",
        "is_active": adb_data.get("available", False) and len(adb_data.get("devices", [])) > 0,
        "latency_label": "< 5ms (Inmune a interferencias)",
        "icon": "usb",
        "description": "Ideal para conectar 3 celulares a un Hub USB con cero pérdida de paquetes y cero jitter."
    })

    # Opción 2: iPhone USB Tethering
    available_routes.append({
        "id": "apple_usb_tethering",
        "title": "iPhone USB Tethering (Apple Mobile Device)",
        "badge": "CABLE LIGHTNING / TYPE-C",
        "ip": apple_usb_info["ip"] or "172.20.10.1",
        "base_url": f"https://{apple_usb_info['ip'] or '172.20.10.1'}:{port}",
        "is_active": apple_usb_info["active"],
        "latency_label": "< 8ms (Cable USB directo)",
        "icon": "phone_iphone",
        "description": "Conecta el iPhone por USB con 'Compartir Internet' activado. Calidad cristalina y estable."
    })

    # Opción 3: Android USB Tethering
    available_routes.append({
        "id": "android_rndis_tethering",
        "title": "Android USB Tethering (RNDIS)",
        "badge": "CABLE TYPE-C",
        "ip": android_rndis_info["ip"] or "192.168.42.129",
        "base_url": f"https://{android_rndis_info['ip'] or '192.168.42.129'}:{port}",
        "is_active": android_rndis_info["active"],
        "latency_label": "< 8ms (Cable USB)",
        "icon": "phone_android",
        "description": "Sin necesidad de instalar ADB: Activa 'Compartir conexión por USB' en los ajustes de Android."
    })

    # Opción 4: Hotspot 5 GHz de Windows
    available_routes.append({
        "id": "windows_hotspot_5g",
        "title": "Hotspot Wi-Fi 5 GHz (Zona Cobertura PC)",
        "badge": "5 GHz ALTA VELOCIDAD",
        "ip": hotspot_info["ip"] or "192.168.137.1",
        "base_url": f"https://{hotspot_info['ip'] or '192.168.137.1'}:{port}",
        "is_active": hotspot_info["active"],
        "latency_label": "< 15ms (Banda limpia 5 GHz)",
        "icon": "wifi_tethering",
        "description": "Zona de cobertura móvil creada directamente desde la laptop o PC en banda 5 GHz."
    })

    # Opción 5: Red Local Wi-Fi
    if wifi_lan_info["active"] and wifi_lan_info["ip"]:
        available_routes.append({
            "id": "wifi_lan",
            "title": "Red Local Wi-Fi / Router de Estudio",
            "badge": "LAN LOCAL",
            "ip": wifi_lan_info["ip"],
            "base_url": f"https://{wifi_lan_info['ip']}:{port}",
            "is_active": True,
            "latency_label": "< 25ms (Router Wi-Fi)",
            "icon": "wifi",
            "description": "Conexión a través del router Wi-Fi del set de grabación."
        })

    # Determinar ruta recomendada por defecto
    recommended_route = "wifi_lan"
    if hotspot_info["active"]:
        recommended_route = "windows_hotspot_5g"
    if adb_data.get("available") and len(adb_data.get("devices", [])) > 0:
        recommended_route = "usb_hub_adb"
    elif apple_usb_info["active"]:
        recommended_route = "apple_usb_tethering"

    return {
        "hotspot_5ghz": hotspot_info,
        "apple_usb": apple_usb_info,
        "android_rndis": android_rndis_info,
        "wifi_lan": wifi_lan_info,
        "usb_adb": adb_data,
        "port": port,
        "recommended_route": recommended_route,
        "available_routes": available_routes,
        "active_ips": all_active_ips
    }
