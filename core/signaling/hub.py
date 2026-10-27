"""
Hub central de señalización WebSocket para Director y Cámaras Móviles.
Soporta señalización WebRTC bidireccional (Offer/Answer/ICE), des-ofuscación mDNS,
telemetría de batería/temperatura y comandos remotos de hardware.
"""

import json
from aiohttp import web
from core.signaling.webrtc_router import WebRtcRouter
from core.infrastructure.json_logger import log_event, log_exception


class SignalingHub:
    def __init__(self, primary_ip_getter):
        self.director_ws = None
        self.cameras = {}  # cam_id (str) -> web.WebSocketResponse
        self.get_primary_ip = primary_ip_getter

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Manejador del socket de señalización."""
        ws = web.WebSocketResponse(heartbeat=15.0)
        await ws.prepare(request)

        registered_role = None
        registered_cam_id = None

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue

                    msg_type = data.get("type")
                    raw_cam_id = data.get("camId") if data.get("camId") is not None else data.get("targetCamId")
                    cam_id_str = str(raw_cam_id) if raw_cam_id is not None else ""

                    # 1. Registro de Rol (Director o Cámara)
                    if msg_type == "register":
                        role = data.get("role")
                        if role == "director":
                            self.director_ws = ws
                            registered_role = "director"
                            print("[WS] 🖥️ Director conectado a la consola")
                            log_event(
                                component="SIGNALING_HUB",
                                message="Consola de Director registrada en el bus WebSocket",
                                details={"client_ip": request.remote, "active_cameras": list(self.cameras.keys())},
                                category="WEBRTC_SIGNALING",
                                action="REGISTER_DIRECTOR"
                            )
                            # Notificar al director de cámaras ya conectadas
                            for active_id, cam_socket in list(self.cameras.items()):
                                if cam_socket and not cam_socket.closed:
                                    await self.director_ws.send_str(json.dumps({
                                        "type": "camera_connected",
                                        "camId": int(active_id) if active_id.isdigit() else active_id
                                    }))
                        elif role == "camera":
                            cam_id = cam_id_str or "1"
                            self.cameras[cam_id] = ws
                            registered_role = "camera"
                            registered_cam_id = cam_id
                            print(f"[WS] 📱 Cámara 0{cam_id} registrada desde {request.remote}")
                            log_event(
                                component="SIGNALING_HUB",
                                message=f"Cámara móvil 0{cam_id} registrada en el bus WebSocket",
                                details={"cam_id": cam_id, "client_ip": request.remote},
                                category="WEBRTC_SIGNALING",
                                action="REGISTER_CAMERA"
                            )
                            if self.director_ws and not self.director_ws.closed:
                                await self.director_ws.send_str(json.dumps({
                                    "type": "camera_connected",
                                    "camId": int(cam_id) if cam_id.isdigit() else cam_id
                                }))

                    # 2. Solicitud de Oferta WebRTC (Director -> Cámara)
                    elif msg_type == "request_offer":
                        cam_ws = self.cameras.get(cam_id_str)
                        if cam_ws and not cam_ws.closed:
                            await cam_ws.send_str(msg.data)

                    # 3. Cámara lista para emitir/recibir oferta (Cámara -> Director)
                    elif msg_type == "ready_for_offer":
                        target_id = cam_id_str or registered_cam_id or "1"
                        if self.director_ws and not self.director_ws.closed:
                            await self.director_ws.send_str(json.dumps({
                                "type": "camera_connected",
                                "camId": int(target_id) if str(target_id).isdigit() else target_id
                            }))

                    # 4. Señalización WebRTC (Offer, Answer, Candidate, ICE)
                    elif msg_type in ("offer", "answer", "candidate", "ice"):
                        target_cam = cam_id_str or registered_cam_id or "1"
                        if "camId" not in data:
                            data["camId"] = int(target_cam) if str(target_cam).isdigit() else target_cam

                        # Obtener IP real del cliente para des-ofuscación de mDNS
                        client_ip = request.remote or "127.0.0.1"
                        if client_ip.startswith("::ffff:"):
                            client_ip = client_ip[7:]
                        director_ip = self.get_primary_ip()
                        sender_real_ip = director_ip if registered_role == "director" else client_ip

                        modified_payload = WebRtcRouter.deobfuscate_mdns(data, sender_real_ip)
                        payload_to_send = modified_payload if modified_payload else json.dumps(data)

                        if msg_type in ("offer", "answer"):
                            log_event(
                                component="SIGNALING_HUB",
                                message=f"Negociación SDP {msg_type.upper()} enrutada para CAM 0{target_cam}",
                                details={
                                    "cam_id": target_cam,
                                    "sender_role": registered_role,
                                    "sender_ip": sender_real_ip,
                                    "mdns_sanitized": bool(modified_payload)
                                },
                                category="WEBRTC_SIGNALING",
                                action=f"SDP_{msg_type.upper()}"
                            )

                        if registered_role == "director":
                            cam_ws = self.cameras.get(str(target_cam))
                            if cam_ws and not cam_ws.closed:
                                await cam_ws.send_str(payload_to_send)
                        else:
                            if self.director_ws and not self.director_ws.closed:
                                await self.director_ws.send_str(payload_to_send)

                    # 5. Control de Luz Tally (Director -> Cámaras)
                    elif msg_type in ("set_tally", "tally"):
                        if cam_id_str and cam_id_str in self.cameras:
                            state = data.get("state")
                            cam_ws = self.cameras.get(cam_id_str)
                            if cam_ws and not cam_ws.closed:
                                await cam_ws.send_str(json.dumps({
                                    "type": "tally",
                                    "state": state,
                                    "activeCam": data.get("activeCam"),
                                    "previewCam": data.get("previewCam")
                                }))
                        else:
                            # Broadcast tally state (activeCam / previewCam) a todas las cámaras
                            for c_id, c_ws in list(self.cameras.items()):
                                if c_ws and not c_ws.closed:
                                    await c_ws.send_str(json.dumps({
                                        "type": "tally",
                                        "activeCam": data.get("activeCam"),
                                        "previewCam": data.get("previewCam"),
                                        "state": "program" if str(data.get("activeCam")) == c_id else (
                                            "preview" if str(data.get("previewCam")) == c_id else "idle"
                                        )
                                    }))

                    # 6. Control de Calidad / Resolución (Director -> Cámaras)
                    elif msg_type == "set_quality":
                        print(f"[CONFIG] Formato solicitado: {data.get('width')}x{data.get('height')} @ {data.get('fps')}fps")
                        for c_id, c_ws in list(self.cameras.items()):
                            if c_ws and not c_ws.closed:
                                await c_ws.send_str(msg.data)

                    # 7. Formato Real Notificado (Cámara -> Director)
                    elif msg_type == "format_update":
                        if self.director_ws and not self.director_ws.closed:
                            await self.director_ws.send_str(msg.data)

                    # 8. Telemetría de Batería y Salud Térmica (Cámaras -> Director)
                    elif msg_type in ("telemetry", "battery", "camera_telemetry"):
                        if self.director_ws and not self.director_ws.closed:
                            await self.director_ws.send_str(msg.data)

                    # 9. Comandos Remotos (Lente, Linterna, Bloqueo)
                    elif msg_type == "camera_command":
                        target_cam = str(data.get("camId"))
                        if target_cam == "all":
                            for c_ws in self.cameras.values():
                                if c_ws and not c_ws.closed:
                                    await c_ws.send_str(msg.data)
                        else:
                            cam_ws = self.cameras.get(target_cam)
                            if cam_ws and not cam_ws.closed:
                                await cam_ws.send_str(msg.data)

                elif msg.type == web.WSMsgType.ERROR:
                    print(f"[WS] Error en conexión WebSocket: {ws.exception()}")

        finally:
            if registered_role == "director":
                if self.director_ws is ws:
                    self.director_ws = None
                print("[WS] 🖥️ Director desconectado")
            elif registered_role == "camera" and registered_cam_id:
                if self.cameras.get(registered_cam_id) is ws:
                    del self.cameras[registered_cam_id]
                print(f"[WS] 📱 Cámara 0{registered_cam_id} desconectada")
                if self.director_ws and not self.director_ws.closed:
                    await self.director_ws.send_str(json.dumps({
                        "type": "camera_disconnected",
                        "camId": int(registered_cam_id) if str(registered_cam_id).isdigit() else registered_cam_id
                    }))

        return ws
