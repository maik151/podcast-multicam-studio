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

        if msg_type == "candidate" and "candidate" in data and data["candidate"]:
            cand_obj = data["candidate"]
            cand_str = cand_obj.get("candidate", "")
            if ".local" in cand_str:
                cand_obj["candidate"] = re.sub(r'[\w\-]+\.local', sender_ip, cand_str)
                data["candidate"] = cand_obj
                modified = True
        elif msg_type in ("offer", "answer"):
            sdp_obj = data.get(msg_type, {})
            sdp_str = sdp_obj.get("sdp", "")
            if ".local" in sdp_str:
                sdp_obj["sdp"] = re.sub(r'[\w\-]+\.local', sender_ip, sdp_str)
                data[msg_type] = sdp_obj
                modified = True

        return json.dumps(data) if modified else None
