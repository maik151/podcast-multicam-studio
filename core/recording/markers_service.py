"""
Gestor de marcadores de clips destacados (REC FLAG) para Podcast Multicam Studio.
Genera reportes simultáneos en formato texto plano y JSON para editores de video.
"""

import os
import json
import datetime

class MarkersService:
    def __init__(self, base_recordings_dir: str):
        self.base_recordings_dir = base_recordings_dir

    def add_marker(self, project: str, episode: str, take: int, timecode_str: str, note: str = "Clip destacado", count: int = 1, current_folder: str = None) -> dict:
        """Registra un marcador de código de tiempo en disco."""
        proj_clean = project.strip().replace(" ", "_")
        ep_clean = episode.strip().replace(" ", "_")
        folder = current_folder if (current_folder and os.path.exists(current_folder)) else os.path.join(self.base_recordings_dir, proj_clean, ep_clean)
        os.makedirs(folder, exist_ok=True)

        marker_txt_path = os.path.join(folder, f"Toma_{take:02d}_Marcadores.txt")
        marker_json_path = os.path.join(folder, f"Toma_{take:02d}_Marcadores.json")

        timestamp_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_txt = f"[{timecode_str}] - FLAG #{count}: {note} ({timestamp_iso})\n"

        with open(marker_txt_path, "a", encoding="utf-8") as f:
            f.write(entry_txt)

        markers_list = []
        if os.path.exists(marker_json_path):
            try:
                with open(marker_json_path, "r", encoding="utf-8") as f:
                    markers_list = json.load(f)
            except Exception:
                markers_list = []

        marker_obj = {
            "index": len(markers_list) + 1,
            "timecode": timecode_str,
            "note": note,
            "created_at": timestamp_iso
        }
        markers_list.append(marker_obj)

        with open(marker_json_path, "w", encoding="utf-8") as f:
            json.dump(markers_list, f, indent=2, ensure_ascii=False)

        print(f"[MARCADOR REC] 🚩 {entry_txt.strip()}")
        return {"status": "marker_added", "marker": marker_obj, "total": len(markers_list)}

    def get_markers(self, project: str, episode: str, take: int, current_folder: str = None) -> list:
        """Obtiene la lista de marcadores registrados para una toma específica."""
        proj_clean = project.strip().replace(" ", "_")
        ep_clean = episode.strip().replace(" ", "_")
        folder = current_folder if (current_folder and os.path.exists(current_folder)) else os.path.join(self.base_recordings_dir, proj_clean, ep_clean)
        marker_json_path = os.path.join(folder, f"Toma_{take:02d}_Marcadores.json")
        if os.path.exists(marker_json_path):
            try:
                with open(marker_json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []
