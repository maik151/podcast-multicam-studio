"""
Puente de Integración USB DroidCam para TX-Studio.
Soporta:
1. Teléfonos Android vía ADB (adb forward tcp:474X tcp:4747).
2. Teléfonos iPhone vía Apple usbmuxd nativo (puerto 27015 -> tcp:4747).
3. Mapeo estricto de 3 cámaras:
   - CAM 01 -> 127.0.0.1:4741
   - CAM 02 -> 127.0.0.1:4742
   - CAM 03 -> 127.0.0.1:4743
"""

import os
import re
import socket
import struct
import plistlib
import threading
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional

from core.network.connection_manager import find_adb_executable, ADB_SERVER_PORT


DROIDCAM_CAMERA_PORTS = {
    1: 4741,
    2: 4742,
    3: 4743
}

DROIDCAM_DEVICE_DEFAULT_PORT = 4747


class UsbMuxForwarder:
    """Cliente nativo en Python puro para comunicarse con el servicio Apple usbmuxd en Windows."""
    
    USBMUXD_PORT = 27015

    @classmethod
    def is_usbmuxd_available(cls) -> bool:
        """Verifica si el servicio usbmuxd de Apple está respondiendo en localhost."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            res = s.connect_ex(("127.0.0.1", cls.USBMUXD_PORT))
            s.close()
            return res == 0
        except Exception:
            return False

    @classmethod
    def list_ios_devices(cls) -> List[Dict[str, Any]]:
        """Consulta la lista de iPhones/iPads conectados por cable USB mediante el socket de usbmuxd."""
        if not cls.is_usbmuxd_available():
            return []

        devices = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect(("127.0.0.1", cls.USBMUXD_PORT))

            req = {
                "MessageType": "ListDevices",
                "ClientVersionString": "TX-Studio-Multicam-1.0",
                "ProgName": "TX-Studio"
            }
            payload = plistlib.dumps(req)
            hdr = struct.pack("<IIII", len(payload) + 16, 1, 8, 1)
            s.sendall(hdr + payload)

            resp_hdr = s.recv(16)
            if len(resp_hdr) == 16:
                length, ver, num, tag = struct.unpack("<IIII", resp_hdr)
                body = s.recv(length - 16)
                res = plistlib.loads(body)
                for item in res.get("DeviceList", []):
                    props = item.get("Properties", {})
                    devices.append({
                        "device_id": item.get("DeviceID"),
                        "serial": props.get("SerialNumber", f"iOS_{item.get('DeviceID')}"),
                        "model": props.get("ProductType", "Apple iPhone"),
                        "name": props.get("DeviceName", "iPhone (USB)"),
                        "connection_type": props.get("ConnectionType", "USB"),
                        "platform": "ios"
                    })
            s.close()
        except Exception:
            pass
        return devices

    @classmethod
    def start_ios_tunnel(cls, local_port: int, device_id: int, target_port: int = DROIDCAM_DEVICE_DEFAULT_PORT) -> threading.Thread:
        """
        Abre un socket TCP local en 127.0.0.1:{local_port} y canaliza todo el tráfico
        directamente al puerto 4747 de la app DroidCam en el iPhone vía usbmuxd.
        """
        stop_event = threading.Event()

        def _relay_worker():
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(("127.0.0.1", local_port))
            server_sock.listen(5)
            server_sock.settimeout(1.0)

            while not stop_event.is_set():
                try:
                    client_conn, _ = server_sock.accept()
                except socket.timeout:
                    continue
                except Exception:
                    break

                # Conectar con usbmuxd para solicitar enlace al puerto del iPhone
                mux_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    mux_sock.settimeout(3.0)
                    # Intentar conectar con el puerto del iPhone (4748 para DroidCam OBS o 4747 para estándar)
                    connected_mux = False
                    for p in (target_port, 4748 if target_port == 4747 else 4747):
                        try:
                            if mux_sock is None:
                                mux_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                mux_sock.settimeout(3.0)
                                mux_sock.connect(("127.0.0.1", cls.USBMUXD_PORT))
                            port_be = ((p << 8) & 0xFF00) | ((p >> 8) & 0x00FF)
                            connect_req = {
                                "MessageType": "Connect",
                                "ClientVersionString": "TX-Studio-1.0",
                                "ProgName": "TX-Studio",
                                "DeviceID": device_id,
                                "PortNumber": port_be
                            }
                            payload = plistlib.dumps(connect_req)
                            hdr = struct.pack("<IIII", len(payload) + 16, 1, 8, 2)
                            mux_sock.sendall(hdr + payload)

                            resp_hdr = mux_sock.recv(16)
                            if len(resp_hdr) == 16:
                                length, _, _, _ = struct.unpack("<IIII", resp_hdr)
                                res_body = mux_sock.recv(length - 16)
                                res = plistlib.loads(res_body)
                                if res.get("Number") == 0:
                                    connected_mux = True
                                    break
                            mux_sock.close()
                            mux_sock = None
                        except Exception:
                            if mux_sock:
                                try: mux_sock.close()
                                except Exception: pass
                            mux_sock = None

                    if not connected_mux:
                        client_conn.close()
                        continue

                    # Iniciar retransmisión bidireccional no bloqueante
                    def _forward(src, dst):
                        try:
                            src.settimeout(5.0)
                            while not stop_event.is_set():
                                chunk = src.recv(65536)
                                if not chunk:
                                    break
                                dst.sendall(chunk)
                        except Exception:
                            pass
                        finally:
                            try:
                                src.close()
                            except Exception:
                                pass
                            try:
                                dst.close()
                            except Exception:
                                pass

                    t1 = threading.Thread(target=_forward, args=(client_conn, mux_sock), daemon=True)
                    t2 = threading.Thread(target=_forward, args=(mux_sock, client_conn), daemon=True)
                    t1.start()
                    t2.start()

                except Exception:
                    try: client_conn.close()
                    except Exception: pass
                    try: mux_sock.close()
                    except Exception: pass

            try: server_sock.close()
            except Exception: pass

        t = threading.Thread(target=_relay_worker, daemon=True, name=f"TX_USBMUX_Port_{local_port}")
        t.stop_event = stop_event
        t.start()
        return t


class DroidCamBridgeManager:
    """Administrador central de puentes USB DroidCam para las 3 cámaras de TX-Studio."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.camera_ports = dict(DROIDCAM_CAMERA_PORTS)
        # cam_id (1..3) -> Device Dict + Status
        self.active_bindings: Dict[int, Dict[str, Any]] = {
            1: None,
            2: None,
            3: None
        }
        self.ios_tunnel_threads: Dict[int, Any] = {}

    def scan_devices(self) -> Dict[str, Any]:
        """
        Escanea todos los dispositivos físicos disponibles (Android e iPhone) conectados por cable USB.
        Cruza con las asignaciones actuales de las 3 cámaras.
        """
        android_devices = []
        adb_bin = find_adb_executable()
        if adb_bin:
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                cmd = [adb_bin, "-P", ADB_SERVER_PORT, "devices", "-l"]
                env = os.environ.copy()
                env["ANDROID_ADB_SERVER_PORT"] = ADB_SERVER_PORT
                out = subprocess.check_output(cmd, env=env, text=True, errors="ignore", timeout=3, creationflags=flags)
                for line in out.splitlines():
                    line = line.strip()
                    if not line or line.startswith("List of devices") or line.startswith("*"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        serial = parts[0]
                        state = parts[1]
                        model_match = re.search(r"model:(\S+)", line)
                        model = model_match.group(1).replace("_", " ") if model_match else "Android Phone"
                        android_devices.append({
                            "id": serial,
                            "serial": serial,
                            "model": model,
                            "name": f"{model} ({serial[:6]}...)",
                            "platform": "android",
                            "state": state,
                            "authorized": state == "device"
                        })
            except Exception:
                pass

        ios_devices = UsbMuxForwarder.list_ios_devices()

        all_devices = android_devices + ios_devices

        # Anotar si algún dispositivo ya está asignado a CAM 01, 02 o 03
        with self._lock:
            for dev in all_devices:
                assigned_cam = None
                for cam_id, binding in self.active_bindings.items():
                    if binding and binding.get("id") == dev.get("id"):
                        assigned_cam = cam_id
                        break
                dev["assigned_cam"] = assigned_cam

        return {
            "devices": all_devices,
            "android_count": len(android_devices),
            "ios_count": len(ios_devices),
            "active_bindings": self.get_bindings_summary()
        }

    def bind_camera(self, cam_id: int, device_id: str, platform: str) -> Dict[str, Any]:
        """
        Asigna un teléfono específico a una cámara (1, 2 o 3) y establece el túnel de puerto USB.
        """
        if cam_id not in self.camera_ports:
            return {"success": False, "message": f"Cámara {cam_id} inválida (rango 1..3)."}

        local_port = self.camera_ports[cam_id]

        with self._lock:
            # Si la cámara ya tenía un enlace previo, liberarlo primero
            self._unbind_unlocked(cam_id)

            if platform.lower() == "android":
                adb_bin = find_adb_executable()
                if not adb_bin:
                    return {"success": False, "message": "ADB no disponible para Android."}

                try:
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    env = os.environ.copy()
                    env["ANDROID_ADB_SERVER_PORT"] = ADB_SERVER_PORT

                    # DroidCam OBS usa puerto 4748 por defecto, DroidCam estándar usa 4747
                    candidate_ports = [4748, 4747]
                    target_port = candidate_ports[0]
                    port_connected = False

                    def _probe_port(lp: int) -> bool:
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(0.6)
                            s.connect(("127.0.0.1", lp))
                            s.sendall(b"GET /video HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
                            chunk = s.recv(128)
                            s.close()
                            return bool(chunk and b"200" in chunk)
                        except Exception:
                            return False

                    # 1. Probar si alguna variante ya está emitiendo en el celular
                    for cand in candidate_ports:
                        cmd = [adb_bin, "-P", ADB_SERVER_PORT, "-s", device_id, "forward", f"tcp:{local_port}", f"tcp:{cand}"]
                        subprocess.call(cmd, env=env, timeout=3, creationflags=flags)
                        if _probe_port(local_port):
                            target_port = cand
                            port_connected = True
                            break

                    # 2. Si no responde, despertar la app DroidCam en el teléfono por si está dormida o en segundo plano
                    if not port_connected:
                        for pkg in ("com.dev47apps.obsdroidcam", "com.dev47apps.droidcam"):
                            try:
                                subprocess.run([adb_bin, "-P", ADB_SERVER_PORT, "-s", device_id, "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"], env=env, timeout=3, creationflags=flags)
                            except Exception:
                                pass
                        # Reintentar sondeo activo durante hasta 3.5s (el sensor y el socket de la app tardan ~1-2.5s en abrir)
                        start_wait = time.time()
                        while time.time() - start_wait < 3.5 and not port_connected:
                            time.sleep(0.5)
                            for cand in candidate_ports:
                                cmd = [adb_bin, "-P", ADB_SERVER_PORT, "-s", device_id, "forward", f"tcp:{local_port}", f"tcp:{cand}"]
                                subprocess.call(cmd, env=env, timeout=2, creationflags=flags)
                                if _probe_port(local_port):
                                    target_port = cand
                                    port_connected = True
                                    break

                    binding_info = {
                        "cam_id": cam_id,
                        "id": device_id,
                        "platform": "android",
                        "local_port": local_port,
                        "target_port": target_port,
                        "stream_url": f"http://127.0.0.1:{local_port}/video",
                        "proxy_url": f"/api/droidcam/feed/{cam_id}",
                        "status": "FORWARDED",
                        "is_streaming": port_connected,
                        "bound_at": time.time()
                    }
                    self.active_bindings[cam_id] = binding_info
                    msg = f"CAM 0{cam_id} enlazada por cable USB a Android ({device_id}) en puerto {local_port} -> cel:{target_port}."
                    if not port_connected:
                        msg += " (Abre la app DroidCam en tu cel si no ves video inmediato)."
                    return {
                        "success": True,
                        "binding": binding_info,
                        "message": msg
                    }
                except Exception as e:
                    return {"success": False, "message": f"Error al ejecutar adb forward: {e}"}

            elif platform.lower() == "ios":
                # Buscar el device_id numérico de usbmuxd
                ios_devs = UsbMuxForwarder.list_ios_devices()
                matched = next((d for d in ios_devs if str(d.get("serial")) == device_id or str(d.get("device_id")) == device_id), None)
                if not matched:
                    # Si no encuentra por ID exacto pero hay 1 solo iPhone conectado, usarlo
                    if len(ios_devs) == 1:
                        matched = ios_devs[0]
                    else:
                        return {"success": False, "message": f"iPhone {device_id} no detectado en usbmuxd."}

                mux_dev_id = matched["device_id"]
                try:
                    thread = UsbMuxForwarder.start_ios_tunnel(local_port, mux_dev_id, DROIDCAM_DEVICE_DEFAULT_PORT)
                    self.ios_tunnel_threads[cam_id] = thread

                    binding_info = {
                        "cam_id": cam_id,
                        "id": matched["serial"],
                        "device_id": mux_dev_id,
                        "platform": "ios",
                        "model": matched.get("model", "iPhone"),
                        "local_port": local_port,
                        "target_port": DROIDCAM_DEVICE_DEFAULT_PORT,
                        "stream_url": f"http://127.0.0.1:{local_port}/video",
                        "proxy_url": f"/api/droidcam/feed/{cam_id}",
                        "status": "FORWARDED",
                        "bound_at": time.time()
                    }
                    self.active_bindings[cam_id] = binding_info
                    return {
                        "success": True,
                        "binding": binding_info,
                        "message": f"CAM 0{cam_id} enlazada por cable USB a iPhone ({matched.get('name')}) en puerto {local_port}."
                    }
                except Exception as e:
                    return {"success": False, "message": f"Error al iniciar túnel usbmuxd con iPhone: {e}"}

            else:
                return {"success": False, "message": f"Plataforma '{platform}' no soportada (use 'android' o 'ios')."}

    def unbind_camera(self, cam_id: int) -> Dict[str, Any]:
        """Libera la asignación de puerto de una cámara."""
        with self._lock:
            return self._unbind_unlocked(cam_id)

    def _unbind_unlocked(self, cam_id: int) -> Dict[str, Any]:
        binding = self.active_bindings.get(cam_id)
        if not binding:
            return {"success": True, "message": f"CAM 0{cam_id} no tenía enlace activo."}

        local_port = binding["local_port"]
        platform = binding["platform"]

        if platform == "android":
            adb_bin = find_adb_executable()
            if adb_bin:
                try:
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    env = os.environ.copy()
                    env["ANDROID_ADB_SERVER_PORT"] = ADB_SERVER_PORT
                    cmd = [adb_bin, "-P", ADB_SERVER_PORT, "forward", "--remove", f"tcp:{local_port}"]
                    subprocess.call(cmd, env=env, timeout=2, creationflags=flags)
                except Exception:
                    pass

        elif platform == "ios":
            thread = self.ios_tunnel_threads.pop(cam_id, None)
            if thread and hasattr(thread, "stop_event"):
                thread.stop_event.set()

        self.active_bindings[cam_id] = None
        return {"success": True, "message": f"CAM 0{cam_id} liberada."}

    def check_stream_health(self, cam_id: int) -> Dict[str, Any]:
        """Verifica si la app DroidCam está activa en el teléfono respondiendo en el puerto local."""
        binding = self.active_bindings.get(cam_id)
        if not binding:
            return {"active": False, "online": False, "message": "No asignado"}

        port = binding["local_port"]
        url = f"http://127.0.0.1:{port}/video"

        is_online = False
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                is_online = resp.status == 200
        except Exception:
            # Fallback conectando socket básico
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.6)
                res = s.connect_ex(("127.0.0.1", port))
                s.close()
                is_online = (res == 0)
            except Exception:
                is_online = False

        return {
            "cam_id": cam_id,
            "port": port,
            "platform": binding.get("platform"),
            "online": is_online,
            "stream_url": url,
            "proxy_url": f"/api/droidcam/feed/{cam_id}"
        }

    def get_bindings_summary(self) -> Dict[int, Any]:
        """Retorna el estado de enlace de las 3 cámaras."""
        res = {}
        for cam_id in (1, 2, 3):
            binding = self.active_bindings.get(cam_id)
            if binding:
                res[cam_id] = {
                    "bound": True,
                    "platform": binding["platform"],
                    "id": binding["id"],
                    "port": binding["local_port"],
                    "stream_url": binding["stream_url"],
                    "proxy_url": binding["proxy_url"]
                }
            else:
                res[cam_id] = {
                    "bound": False,
                    "port": self.camera_ports[cam_id]
                }
        return res


# Instancia singleton para compartir en el backend
droidcam_bridge = DroidCamBridgeManager()
