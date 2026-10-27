"""
Enrutador de señalización WebRTC y des-ofuscador mDNS para LAN y Hotspot.
"""

import re
import json

class WebRtcRouter:
    @staticmethod
    def deobfuscate_mdns(data: dict, sender_ip: str) -> str:
        """
        Reemplaza identificadores mDNS '.local' ofuscados por la IP real
        del emisor en candidatos ICE y descripciones SDP.
        """
        msg_type = data.get("type")
        modified = False

        if msg_type in ("candidate", "ice") and "candidate" in data and data["candidate"]:
            cand_obj = data["candidate"]
            if isinstance(cand_obj, dict):
                cand_str = cand_obj.get("candidate", "")
                if ".local" in cand_str:
                    cand_obj["candidate"] = re.sub(r'[\w\-]+\.local', sender_ip, cand_str)
                    data["candidate"] = cand_obj
                    modified = True
            elif isinstance(cand_obj, str) and ".local" in cand_obj:
                data["candidate"] = re.sub(r'[\w\-]+\.local', sender_ip, cand_obj)
                modified = True
        elif msg_type in ("offer", "answer"):
            sdp_obj = data.get("sdp") if data.get("sdp") is not None else data.get(msg_type, {})
            if isinstance(sdp_obj, dict):
                sdp_str = sdp_obj.get("sdp", "")
                if ".local" in sdp_str:
                    sdp_obj["sdp"] = re.sub(r'[\w\-]+\.local', sender_ip, sdp_str)
                    if "sdp" in data:
                        data["sdp"] = sdp_obj
                    else:
                        data[msg_type] = sdp_obj
                    modified = True
            elif isinstance(sdp_obj, str) and ".local" in sdp_obj:
                data["sdp"] = re.sub(r'[\w\-]+\.local', sender_ip, sdp_obj)
                modified = True

        return json.dumps(data) if modified else None
