"""
Servicio de grabación a disco (Take Engine) para Podcast Multicam Studio.
Maneja tomas numeradas y streaming continuo de chunks binarios directamente al almacenamiento.
"""

import os
import sys
import datetime
import subprocess


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        print(msg.encode(encoding, errors="replace").decode(encoding))

class RecorderService:
    def __init__(self, base_recordings_dir: str):
        self.base_recordings_dir = base_recordings_dir
        self.current_recording_file = None
        self.current_recording_path = None
        self.current_recording_folder = None
        self.total_bytes_written = 0
        self.is_active = False

    def start_take(
        self,
        project: str = "Podcast",
        episode: str = "Episodio_01",
        take: int = 1,
        resolution: str = "1080p",
        fps: int = 60,
        ext: str = "webm",
        custom_name: str = ""
    ) -> dict:
        """Inicia un nuevo archivo físico de toma en disco."""
        proj_clean = project.strip().replace(" ", "_")
        ep_clean = episode.strip().replace(" ", "_")
        ext_clean = ext.strip().replace(".", "")
        custom_clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in (custom_name or "").strip())

        # Sellar toma anterior de forma segura si quedó abierta
        if self.current_recording_file and not self.current_recording_file.closed:
            _safe_print("[RECORDER] ⚠️ Sello automático de toma previa antes de abrir nueva toma.")
            self.stop_take()

        self.current_recording_folder = os.path.join(self.base_recordings_dir, proj_clean, ep_clean)
        os.makedirs(self.current_recording_folder, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_clean:
            filename = f"{custom_clean}_Toma_{take:02d}_{resolution}_{fps}fps_{timestamp}.{ext_clean}"
        else:
            filename = f"Toma_{take:02d}_{resolution}_{fps}fps_{timestamp}.{ext_clean}"
        self.current_recording_path = os.path.join(self.current_recording_folder, filename)
        self.total_bytes_written = 0

        self.current_recording_file = open(self.current_recording_path, "wb")
        self.is_active = True
        print(f"\n[RECORDER] Iniciando archivo en disco: {self.current_recording_path} ({resolution} @ {fps}fps)")

        return {
            "status": "recording_started",
            "file": filename,
            "path": self.current_recording_path,
            "folder": self.current_recording_folder,
            "take": take
        }

    def write_chunk(self, chunk_data: bytes) -> dict:
        """Escribe un chunk binario de audio/video y hace flush a disco."""
        if self.is_active and self.current_recording_file and not self.current_recording_file.closed:
            if chunk_data:
                self.current_recording_file.write(chunk_data)
                self.current_recording_file.flush()
                self.total_bytes_written += len(chunk_data)
                total_mb = round(self.total_bytes_written / (1024 * 1024), 2)
                return {"status": "chunk_written", "bytes": len(chunk_data), "total_mb": total_mb}
        return {"status": "error", "message": "No hay archivo de grabación activo"}

    def stop_take(self) -> dict:
        """Finaliza y sella el archivo de video en el disco duro."""
        if self.current_recording_file and not self.current_recording_file.closed:
            self.current_recording_file.flush()
            self.current_recording_file.close()

            file_size_bytes = os.path.getsize(self.current_recording_path) if os.path.exists(self.current_recording_path) else 0
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
            _safe_print(f"[RECORDER] ✅ Toma sellada exitosamente: {self.current_recording_path} ({file_size_mb} MB)\n")

            saved_path = self.current_recording_path
            saved_folder = self.current_recording_folder

            self.current_recording_file = None
            self.current_recording_path = None
            self.is_active = False

            return {
                "status": "recording_saved",
                "path": saved_path,
                "folder": saved_folder,
                "size_mb": file_size_mb,
                "bytes": file_size_bytes
            }
        return {"status": "error", "message": "No había archivo de grabación abierto"}

    def open_folder(self) -> bool:
        """Abre la carpeta de grabaciones en el Explorador de Windows."""
        folder = self.current_recording_folder or self.base_recordings_dir
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
            return True
        return False
