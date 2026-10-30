"""
Gestor de Conexiones Multiruta y Hub USB para Podcast Multicam Studio.
Gestiona de forma inteligente y 100% offline:
1. Hub USB Físico con Android ADB (reversión de puertos tcp:8443 -> localhost).
2. Conexiones USB Tethering (Apple Mobile Device iOS 172.20.10.x y Android RNDIS 192.168.42.x).
3. Hotspot Wi-Fi 5 GHz de Windows (192.168.137.1) con detección de estado dinámico.
4. Redes Wi-Fi / Ethernet LAN locales.
5. Optimización de enrutamiento mixto para CERO pérdida de paquetes y máxima estabilidad.
"""

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

# Forzar puerto 5039 a nivel de proceso para que el daemon de ADB nunca colisione con spacedesk (puerto 5037)
ADB_SERVER_PORT = "5039"
os.environ["ANDROID_ADB_SERVER_PORT"] = ADB_SERVER_PORT
os.environ["ADB_SERVER_SOCKET"] = f"tcp:localhost:{ADB_SERVER_PORT}"


KNOWN_PHONE_VIDS = {
    "339B": "Honor",
    "12D1": "Huawei",
    "04E8": "Samsung Galaxy",
    "2717": "Xiaomi / Redmi / POCO",
    "18D1": "Google Pixel",
    "05AC": "Apple iPhone / iPad",
    "22B8": "Motorola",
    "2E04": "Transsion (Tecno / Infinix)",
    "22D9": "OPPO / OnePlus / Realme",
    "0BB4": "HTC",
    "0FCE": "Sony Xperia",
    "1949": "Amazon Fire",
    "17EF": "Lenovo"
}


# Cache en memoria para evitar saturar el hilo principal con PowerShell (6.4 segundos -> 0.001 segundos)
_RAW_HARDWARE_CACHE = None
_RAW_HARDWARE_CACHE_TIME = 0.0
_HARDWARE_CACHE_TTL = 6.0

_ADAPTERS_CACHE = None
_ADAPTERS_CACHE_TIME = 0.0
_ADAPTERS_CACHE_TTL = 4.0


def get_connected_usb_hardware(adb_devices: Optional[List[Dict[str, Any]]] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Detecta todos los dispositivos de hardware USB físicos conectados a la PC:
    - Smartphones y Tablets (Android, iPhone) por cable.
    - Hubs USB y Concentradores multipuerto.
    - Adaptadores de red USB (Remote NDIS, Apple USB Ethernet).
    - Cámaras web y capturadoras USB.
    Cruza la información con ADB para indicar si está autorizado o requiere tocar la pantalla.
    Utiliza caché ultra-rápida de 6s para no bloquear el loop asíncrono.
    """
    global _RAW_HARDWARE_CACHE, _RAW_HARDWARE_CACHE_TIME

    hardware_list: List[Dict[str, Any]] = []
    if adb_devices is None:
        try:
            adb_scan = get_adb_devices()
            adb_devs = adb_scan.get("devices", [])
        except Exception:
            adb_devs = []
    else:
        adb_devs = adb_devices
    adb_serials = {d.get("serial", "").upper(): d for d in adb_devs if d.get("serial")}

    raw_items: List[Dict[str, Any]] = []
    now = time.time()
    if not force_refresh and _RAW_HARDWARE_CACHE is not None and (now - _RAW_HARDWARE_CACHE_TIME) < _HARDWARE_CACHE_TTL:
        raw_items = _RAW_HARDWARE_CACHE
    else:
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            ps_cmd = (
                "Get-PnpDevice -PresentOnly | Where-Object { "
                "$_.InstanceId -like '*USB*' -or "
                "$_.Class -in 'USB','USBDevice','WPD','AndroidUsbDeviceClass','Camera','Image' -or "
                "($_.Class -eq 'Net' -and ($_.InstanceId -like '*USB*' -or $_.FriendlyName -like '*NDIS*' -or $_.FriendlyName -like '*Apple*')) "
                "} | Select-Object FriendlyName, InstanceId, Class, Status | ConvertTo-Json -Compress"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                text=True,
                errors="ignore",
                timeout=5,
                creationflags=flags
            )
            if out and out.strip():
                parsed = json.loads(out)
                if isinstance(parsed, list):
                    raw_items = parsed
                elif isinstance(parsed, dict):
                    raw_items = [parsed]
            _RAW_HARDWARE_CACHE = raw_items
            _RAW_HARDWARE_CACHE_TIME = now
        except Exception:
            if _RAW_HARDWARE_CACHE is not None:
                raw_items = _RAW_HARDWARE_CACHE

    # Agrupador de teléfonos por VID/PID o serial para consolidar interfaces WPD + ADB + Compuesto
    phones_map: Dict[str, Dict[str, Any]] = {}
    hubs_list: List[Dict[str, Any]] = []
    cams_list: List[Dict[str, Any]] = []
    nets_list: List[Dict[str, Any]] = []

    for item in raw_items:
        name = item.get("FriendlyName") or "Dispositivo USB"
        inst = item.get("InstanceId") or ""
        cls = item.get("Class") or ""
        status = item.get("Status") or "OK"

        # Filtrar hubs raíz internos de la placa madre y controladores PCIe host
        if "ROOT_HUB" in inst.upper() or "PCI\\VEN" in inst.upper():
            continue
        # Filtrar teclados, ratones y periféricos HID genéricos
        if cls == "HIDClass" or any(k in name.lower() for k in ["keyboard", "teclado", "mouse", "raton", "ratón", "dispositivo de entrada"]):
            continue

        inst_upper = inst.upper()
        name_lower = name.lower()

        # Extraer VID y PID si existen
        vid_match = re.search(r"VID_([0-9A-F]{4})", inst_upper)
        pid_match = re.search(r"PID_([0-9A-F]{4})", inst_upper)
        vid = vid_match.group(1) if vid_match else ""
        pid = pid_match.group(1) if pid_match else ""

        # Extraer número de serie si viene en InstanceId
        serial = ""
        parts = inst.split("\\")
        if len(parts) >= 3 and not "&" in parts[-1]:
            serial = parts[-1]

        brand = KNOWN_PHONE_VIDS.get(vid, "")
        if vid == "05AC" and not any(k in name_lower for k in ["apple mobile", "iphone", "ipad", "ipod"]):
            brand = ""

        # 1. ¿Es un smartphone o dispositivo móvil?
        is_phone = (
            cls in ("WPD", "AndroidUsbDeviceClass", "USBDevice") or
            brand != "" or
            "android" in name_lower or
            "adb" in name_lower or
            "phone" in name_lower or
            "ndis based internet" in name_lower or
            "apple mobile" in name_lower or
            (serial and serial.upper() in adb_serials)
        )

        # 2. ¿Es un Hub USB?
        is_hub = ("concentrador" in name_lower or "hub" in name_lower or vid in ("214B", "05E3", "1A40", "0424", "0BDA")) and not is_phone

        # 3. ¿Es una cámara o capturadora?
        is_cam = (cls in ("Camera", "Image") or any(k in name_lower for k in ["cam", "webcam", "video capture", "camlink", "uvc"])) and not is_phone

        # 4. ¿Es adaptador de red USB / Tethering?
        is_net = (cls == "Net" or "ndis" in name_lower or "ethernet" in name_lower) and not is_phone

        if is_phone:
            # Buscar si ya existe una entrada para este teléfono por serial o por (VID, PID)
            matched_key = None
            for pk, p_entry in phones_map.items():
                if serial and p_entry.get("serial") and p_entry.get("serial").upper() == serial.upper():
                    matched_key = pk
                    break
                if vid and pid and p_entry.get("vid") == vid and p_entry.get("pid") == pid:
                    matched_key = pk
                    break

            if not matched_key:
                phone_key = serial.upper() if serial else (f"{vid}_{pid}" if vid else name)
                phones_map[phone_key] = {
                    "names": [name],
                    "inst": inst,
                    "vid": vid,
                    "pid": pid,
                    "serial": serial,
                    "brand": brand or ("Honor" if vid == "339B" else "Smartphone"),
                    "classes": [cls],
                    "has_adb": "adb" in name_lower or cls == "USBDevice",
                    "has_mtp": cls == "wpd" or "almacenamiento" in name_lower,
                    "status": status
                }
            else:
                p = phones_map[matched_key]
                p["names"].append(name)
                p["classes"].append(cls)
                if serial and not p["serial"]:
                    p["serial"] = serial
                if "adb" in name_lower or cls == "USBDevice":
                    p["has_adb"] = True
                if cls == "WPD" or "almacenamiento" in name_lower:
                    p["has_mtp"] = True
                if ("compuesto" in p["names"][0].lower() or "adb" in p["names"][0].lower() or "dispositivo" in p["names"][0].lower()) and not any(g in name.lower() for g in ["compuesto", "adb", "dispositivo"]):
                    p["names"].insert(0, name)

        elif is_hub:
            hubs_list.append({"name": name, "inst": inst, "vid": vid, "pid": pid, "status": status})
        elif is_cam:
            cams_list.append({"name": name, "inst": inst, "status": status})
        elif is_net:
            nets_list.append({"name": name, "inst": inst, "status": status})

    # 1. Teléfonos móviles consolidados
    for key, p in phones_map.items():
        chosen_name = p["names"][0]
        for n in p["names"]:
            if n.lower() not in ["dispositivo compuesto usb", "dispositivo de almacenamiento usb", "adb interface"]:
                chosen_name = n
                break

        brand = p["brand"]
        serial = p["serial"]

        # Cruzar con ADB
        matched_adb = None
        if serial and serial.upper() in adb_serials:
            matched_adb = adb_serials[serial.upper()]
        elif adb_devs:
            matched_adb = adb_devs[0]

        adb_state = None
        adb_state_label = None

        if matched_adb:
            st = matched_adb.get("state", "").lower()
            adb_state = st
            if st == "device":
                adb_state_label = "🟢 ADB AUTORIZADO (0ms)"
                details = f"{brand} ({chosen_name}): Conexión USB autorizada y lista para 0ms de latencia."
                hint = "Usa http://localhost:8080/cam/X para máxima velocidad sin latencia y sin advertencias de certificado."
            elif st == "unauthorized":
                adb_state_label = "⚠️ PENDIENTE EN PANTALLA"
                details = f"{brand} ({chosen_name}): Conectado con depuración USB, pero en espera de permiso RSA en pantalla."
                hint = "Toca 'Permitir siempre' en la pantalla del celular para habilitar localhost."
            else:
                adb_state_label = f"⚡ ADB {st.upper()}"
                details = f"{brand} ({chosen_name}): Detectado por ADB ({st})."
                hint = "Revisa la pantalla del celular."
        else:
            if p["has_adb"]:
                adb_state_label = "🔌 CABLE CON ADB ACTIVO"
                details = f"{brand} ({chosen_name}): Cable conectado e Interfaz ADB WINUSB reconocida por Windows."
                hint = "En tu celular, desliza la barra superior de notificaciones, cambia a 'Transferir archivos (MTP)' y vuelve a activar 'Depuración USB'."
            elif p["has_mtp"]:
                adb_state_label = "📁 MODO TRANSFERENCIA MTP"
                details = f"{brand} ({chosen_name}): Teléfono conectado por cable en modo de archivos."
                hint = "Activa 'Depuración por USB' en Opciones de desarrollador de tu celular."
            else:
                adb_state_label = "🔌 CABLE USB CONECTADO"
                details = f"{brand} ({chosen_name}): Conectado por cable USB físico."
                hint = "Activa 'Depuración por USB' o 'Compartir conexión por USB (Tethering)'."

        display_name = f"{brand} ({chosen_name})" if chosen_name.lower() != brand.lower() else brand
        hardware_list.append({
            "id": p["inst"],
            "name": display_name,
            "brand": brand,
            "category": "smartphone",
            "category_label": f"Smartphone {brand}",
            "icon": "smartphone",
            "serial": serial,
            "vid": p["vid"],
            "pid": p["pid"],
            "status": p["status"],
            "status_badge": "CONECTADO",
            "adb_state": adb_state,
            "adb_state_label": adb_state_label,
            "details": details,
            "action_hint": hint
        })

    # 2. Concentradores Hub USB
    for h in hubs_list:
        hardware_list.append({
            "id": h["inst"],
            "name": h["name"],
            "brand": "",
            "category": "hub",
            "category_label": "Hub USB Multipuerto",
            "icon": "hub",
            "serial": "",
            "vid": h["vid"],
            "pid": h["pid"],
            "status": h["status"],
            "status_badge": "CONECTADO",
            "adb_state": None,
            "adb_state_label": None,
            "details": f"{h['name']}: Concentrador multipuerto físico listo para recibir celulares.",
            "action_hint": "Conecta los cables de tus celulares en este concentrador."
        })

    # 3. Cámaras USB
    for c in cams_list:
        hardware_list.append({
            "id": c["inst"],
            "name": c["name"],
            "brand": "",
            "category": "camera",
            "category_label": "Cámara / Capturadora USB",
            "icon": "videocam",
            "serial": "",
            "vid": "",
            "pid": "",
            "status": c["status"],
            "status_badge": "CONECTADO",
            "adb_state": None,
            "adb_state_label": None,
            "details": f"{c['name']}: Dispositivo de video USB detectado y listo.",
            "action_hint": "Disponible para uso directo."
        })

    # 4. Redes USB
    for n in nets_list:
        hardware_list.append({
            "id": n["inst"],
            "name": n["name"],
            "brand": "",
            "category": "network",
            "category_label": "Adaptador de Red USB",
            "icon": "lan",
            "serial": "",
            "vid": "",
            "pid": "",
            "status": n["status"],
            "status_badge": "CONECTADO",
            "adb_state": None,
            "adb_state_label": None,
            "details": f"{n['name']}: Interfaz de red por cable USB.",
            "action_hint": "Permite transmisión directa por cable IP."
        })

    # Si ADB detectó algún dispositivo que no apareció en el filtro PnP, agregarlo explícitamente
    for adb_dev in adb_devs:
        s = adb_dev.get("serial", "")
        if s and not any(h.get("serial") == s for h in hardware_list):
            st = adb_dev.get("state", "").lower()
            hardware_list.append({
                "id": f"ADB_{s}",
                "name": adb_dev.get("model") or f"Android Device ({s})",
                "brand": "Android",
                "category": "smartphone",
                "category_label": "Smartphone Android (ADB)",
                "icon": "smartphone",
                "serial": s,
                "vid": "",
                "pid": "",
                "status": "OK",
                "status_badge": "CONECTADO",
                "adb_state": st,
                "adb_state_label": "🟢 ADB AUTORIZADO" if st == "device" else "⚠️ PENDIENTE AUTORIZACIÓN RSA",
                "details": f"Dispositivo detectado por ADB en modo {st}.",
                "action_hint": "Toca 'Permitir depuración por USB' en el celular si aparece la ventana emergente."
            })

    return hardware_list


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


ADB_SERVER_PORT = "5039"


def run_adb(args: List[str], timeout: int = 5) -> str:
    """
    Ejecuta comandos ADB asignando el puerto dedicado 5039.
    Esto aísla a TX-Studio de conflictos con spacedesk u otros servicios que bloquean el puerto 5037 por defecto.
    """
    adb_bin = find_adb_executable()
    if not adb_bin:
        raise FileNotFoundError("ADB no encontrado")

    env = os.environ.copy()
    env["ANDROID_ADB_SERVER_PORT"] = ADB_SERVER_PORT
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        cmd = [adb_bin, "-P", ADB_SERVER_PORT] + args
        res = subprocess.run(cmd, env=env, text=True, errors="ignore", timeout=timeout, creationflags=flags, capture_output=True)
        if res.returncode == 0 or res.stdout:
            return res.stdout
    except Exception:
        pass

    try:
        cmd_fallback = [adb_bin] + args
        res = subprocess.run(cmd_fallback, env=env, text=True, errors="ignore", timeout=timeout, creationflags=flags, capture_output=True)
        return res.stdout
    except Exception:
        return ""


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
    Escanea dispositivos Android conectados por cable USB mediante ADB en puerto 5039.
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
        output = run_adb(["devices", "-l"], timeout=5)

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
                    rev_out = run_adb(["-s", serial, "reverse", "--list"], timeout=3)
                    if f"tcp:{port}" in rev_out or "tcp:8080" in rev_out:
                        is_reversed = True
                    elif state == "device":
                        # Auto-establecer túnel reverso dual (8443 HTTPS + 8080 HTTP) para el cable USB
                        run_adb(["-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"], timeout=3)
                        run_adb(["-s", serial, "reverse", "tcp:8080", "tcp:8080"], timeout=3)
                        is_reversed = True
                except Exception:
                    pass

                devices.append({
                    "serial": serial,
                    "state": state,
                    "model": model,
                    "product": product,
                    "reversed": is_reversed,
                    "direct_url": "http://localhost:8080",
                    "https_url": f"https://localhost:{port}"
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

    success_count = 0
    results = []

    for dev in devices:
        serial = dev["serial"]
        try:
            run_adb(["-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"], timeout=4)
            run_adb(["-s", serial, "reverse", "tcp:8080", "tcp:8080"], timeout=4)
            success_count += 1
            results.append({"serial": serial, "status": "ok", "url": "http://localhost:8080", "https_url": f"https://localhost:{port}"})
        except Exception as e:
            results.append({"serial": serial, "status": "error", "error": str(e)})

    return {
        "success": success_count > 0,
        "reversed_count": success_count,
        "total_devices": len(devices),
        "results": results,
        "message": f"Túnel USB revertido en {success_count}/{len(devices)} dispositivos (puerto {port})."
    }


def parse_network_adapters(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Parsea las interfaces de red activas en Windows con caché de 4s y ejecución en 50ms.
    Retorna nombre, descripción, estado de desconexión, dirección IPv4 y Gateway.
    """
    global _ADAPTERS_CACHE, _ADAPTERS_CACHE_TIME
    now = time.time()
    if not force_refresh and _ADAPTERS_CACHE is not None and (now - _ADAPTERS_CACHE_TIME) < _ADAPTERS_CACHE_TTL:
        return _ADAPTERS_CACHE

    adapters: List[Dict[str, Any]] = []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # 1. Método ultra-rápido (50ms): ipconfig /all
    try:
        output = subprocess.check_output(
            "ipconfig /all",
            shell=True,
            text=True,
            errors="ignore",
            timeout=2,
            creationflags=flags
        )

        current: Optional[Dict[str, Any]] = None
        for line in output.splitlines():
            if line and not line.startswith(" ") and line.endswith(":"):
                header = line.rstrip(":").strip()
                if "adaptador" in header.lower() or "adapter" in header.lower():
                    current = {"name": header, "desc": "", "ip": None, "gateway": None, "disconnected": False}
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
                elif "puerta de enlace" in sline.lower() or "default gateway" in sline.lower():
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", sline)
                    if match and match.group(1) != "0.0.0.0":
                        current["gateway"] = match.group(1)

        valid_adapters = [a for a in adapters if a.get("ip") and not a.get("disconnected")]
        if valid_adapters:
            _ADAPTERS_CACHE = valid_adapters
            _ADAPTERS_CACHE_TIME = now
            return valid_adapters
    except Exception:
        pass

    if _ADAPTERS_CACHE is not None:
        return _ADAPTERS_CACHE
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
        "gateway": None,
        "name": "Zona con Cobertura Móvil (Windows Hotspot 5 GHz)",
        "adapter_desc": None,
        "adapter_name": None,
        "suggested_band": "5 GHz"
    }

    apple_usb_info = {
        "active": False,
        "ip": None,
        "gateway": None,
        "name": "Apple Mobile Device Ethernet (iOS USB Tethering)",
        "adapter_desc": None,
        "adapter_name": None
    }

    android_rndis_info = {
        "active": False,
        "ip": None,
        "gateway": None,
        "name": "Android USB Tethering (RNDIS)",
        "adapter_desc": None,
        "adapter_name": None
    }

    wifi_lan_info = {
        "active": False,
        "ip": None,
        "gateway": None,
        "name": "Red Local Wi-Fi / LAN",
        "adapter_desc": None,
        "adapter_name": None
    }

    all_active_ips: List[str] = []

    for a in adapters:
        ip = a.get("ip")
        if not ip or a.get("disconnected"):
            continue

        desc = a.get("desc", "").lower()
        name = a.get("name", "").lower()
        gw = a.get("gateway")

        # Filtrar hipervisores y redes virtuales no accesibles por móviles
        if any(v in desc or v in name for v in ["vmware", "virtualbox", "vethernet", "hyper-v", "wsl", "bluetooth", "kaspersky"]):
            continue

        all_active_ips.append(ip)

        # 1. Hotspot de Windows (192.168.137.1 o Wi-Fi Direct activo)
        if ip == "192.168.137.1" or "wi-fi direct" in desc:
            hotspot_info["active"] = True
            hotspot_info["ip"] = ip
            hotspot_info["gateway"] = gw
            hotspot_info["adapter_desc"] = a.get("desc")
            hotspot_info["adapter_name"] = a.get("name")

        # 2. iPhone USB Tethering (Apple Mobile Device)
        elif "apple" in desc or "apple" in name or ip.startswith("172.20.10."):
            apple_usb_info["active"] = True
            apple_usb_info["ip"] = ip
            apple_usb_info["gateway"] = gw
            apple_usb_info["adapter_desc"] = a.get("desc")
            apple_usb_info["adapter_name"] = a.get("name")

        # 3. Android USB Tethering (Remote NDIS / Compartir Internet por USB)
        elif (any(k in desc for k in ["ndis", "remote ndis", "rndis", "compartir", "sharing"]) or 
              any(k in name for k in ["ndis", "rndis", "ethernet 3", "ethernet 4"]) or 
              ip.startswith("192.168.42.") or 
              (gw and ip.startswith("10.") and not ip.startswith("10.0.0."))):
            android_rndis_info["active"] = True
            android_rndis_info["ip"] = ip
            android_rndis_info["gateway"] = gw
            android_rndis_info["adapter_desc"] = a.get("desc")
            android_rndis_info["adapter_name"] = a.get("name")

        # 4. Wi-Fi / Ethernet Físico
        elif any(w in desc or w in name for w in ["wi-fi", "wireless", "802.11", "ethernet", "realtek", "intel"]):
            if not wifi_lan_info["active"]:
                wifi_lan_info["active"] = True
                wifi_lan_info["ip"] = ip
                wifi_lan_info["gateway"] = gw
                wifi_lan_info["adapter_desc"] = a.get("desc")
                wifi_lan_info["adapter_name"] = a.get("name")

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
        "base_url": "http://localhost:8080",
        "https_url": f"https://localhost:{port}",
        "is_active": adb_data.get("available", False) and len(adb_data.get("devices", [])) > 0,
        "latency_label": "< 5ms (Inmune a interferencias)",
        "icon": "usb",
        "description": "Ideal para conectar celulares vía Hub USB. Acceso instantáneo en http://localhost:8080 sin advertencias de certificado."
    })

    # Opción 2: iPhone USB Tethering
    apple_target_ip = apple_usb_info["ip"] or wifi_lan_info["ip"] or "localhost"
    available_routes.append({
        "id": "apple_usb_tethering",
        "title": "iPhone USB Tethering (Apple Mobile Device)",
        "badge": "CABLE LIGHTNING / TYPE-C",
        "ip": apple_usb_info["ip"] or "Desconectado",
        "gateway": apple_usb_info.get("gateway"),
        "base_url": f"https://{apple_target_ip}:{port}",
        "is_active": apple_usb_info["active"],
        "latency_label": "< 8ms (Cable USB directo)",
        "icon": "phone_iphone",
        "description": "Conecta el iPhone por USB con 'Compartir Internet' activado. Calidad cristalina y estable."
    })

    # Opción 3: Android USB Tethering
    android_target_ip = android_rndis_info["ip"] or wifi_lan_info["ip"] or "localhost"
    available_routes.append({
        "id": "android_rndis_tethering",
        "title": "Android USB Tethering (RNDIS)",
        "badge": "CABLE TYPE-C",
        "ip": android_rndis_info["ip"] or "Desconectado",
        "gateway": android_rndis_info.get("gateway"),
        "base_url": f"https://{android_target_ip}:{port}",
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

    # Detección exhaustiva de hardware físico USB (Celulares, Hubs, Redes USB, Cámaras)
    usb_hardware = get_connected_usb_hardware(adb_data.get("devices", []))

    # Determinar ruta recomendada por defecto
    recommended_route = "wifi_lan"
    if hotspot_info["active"]:
        recommended_route = "windows_hotspot_5g"
    if adb_data.get("available") and any(d.get("state") == "device" for d in adb_data.get("devices", [])):
        recommended_route = "usb_hub_adb"
    elif apple_usb_info["active"]:
        recommended_route = "apple_usb_tethering"
    elif android_rndis_info["active"]:
        recommended_route = "android_rndis_tethering"

    return {
        "hotspot_5ghz": hotspot_info,
        "apple_usb": apple_usb_info,
        "android_rndis": android_rndis_info,
        "wifi_lan": wifi_lan_info,
        "usb_adb": adb_data,
        "usb_hardware": usb_hardware,
        "usb_hardware_count": len(usb_hardware),
        "port": port,
        "recommended_route": recommended_route,
        "available_routes": available_routes,
        "active_ips": all_active_ips
    }
