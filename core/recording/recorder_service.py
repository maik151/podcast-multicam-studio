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
        self.last_saved_path = None
        self.last_saved_folder = None
        self.total_bytes_written = 0
        self.is_active = False

    @staticmethod
    def _sanitize_name(value: str, fallback: str = "RUTA33") -> str:
        raw = (value or "").strip().replace(" ", "_")
        cleaned = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in raw).strip("_")
        return cleaned or fallback

    def start_take(
        self,
        project: str = "RUTA33",
        episode: str = "Episodio_01",
        take: int = 1,
        resolution: str = "1080p",
        fps: int = 60,
        ext: str = "mp4",
        custom_name: str = ""
    ) -> dict:
        """Inicia un nuevo archivo físico de toma en disco."""
        proj_clean = self._sanitize_name(project, "RUTA33")
        ep_clean = self._sanitize_name(episode, "Episodio_01")
        ext_clean = (ext or "mp4").strip().replace(".", "").lower() or "mp4"
        custom_clean = self._sanitize_name(custom_name, "") if (custom_name or "").strip() else ""

        # Si el usuario escribió la extensión dentro del nombre (ej. toma1.mp4), removerla
        if custom_clean.lower().endswith(f"_{ext_clean}"):
            custom_clean = custom_clean[:-(len(ext_clean) + 1)]

        # Sellar toma anterior de forma segura si quedó abierta
        if self.current_recording_file and not self.current_recording_file.closed:
            _safe_print("[RECORDER] Sello automatico de toma previa antes de abrir nueva toma.")
            self.stop_take(auto_open=False)

        if custom_clean:
            # Flujo por Grupo de Tomas (Proyecto -> toma1.mp4, toma2.mp4...)
            self.current_recording_folder = os.path.join(self.base_recordings_dir, proj_clean)
            os.makedirs(self.current_recording_folder, exist_ok=True)

            base_candidate = f"{custom_clean}.{ext_clean}"
            candidate_path = os.path.join(self.current_recording_folder, base_candidate)
            if not os.path.exists(candidate_path):
                filename = base_candidate
            else:
                suffix = 2
                while True:
                    alt_name = f"{custom_clean}_{suffix:02d}.{ext_clean}"
                    alt_path = os.path.join(self.current_recording_folder, alt_name)
                    if not os.path.exists(alt_path):
                        filename = alt_name
                        break
                    suffix += 1
        else:
            # Flujo clasico compatible con suites de pruebas legacy
            self.current_recording_folder = os.path.join(self.base_recordings_dir, proj_clean, ep_clean)
            os.makedirs(self.current_recording_folder, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Toma_{take:02d}_{resolution}_{fps}fps_{timestamp}.{ext_clean}"

        self.current_recording_path = os.path.join(self.current_recording_folder, filename)
        self.total_bytes_written = 0

        self.current_recording_file = open(self.current_recording_path, "wb")
        self.is_active = True
        _safe_print(f"\n[RECORDER] Iniciando archivo en disco: {self.current_recording_path} ({resolution} @ {fps}fps)")

        return {
            "status": "recording_started",
            "project": proj_clean,
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

    def stop_take(self, auto_open: bool = False) -> dict:
        """Finaliza y sella el archivo de video en el disco duro."""
        if self.current_recording_file and not self.current_recording_file.closed:
            self.current_recording_file.flush()
            self.current_recording_file.close()

            file_size_bytes = os.path.getsize(self.current_recording_path) if os.path.exists(self.current_recording_path) else 0
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
            _safe_print(f"[RECORDER] Toma sellada exitosamente: {self.current_recording_path} ({file_size_mb} MB)\n")

            saved_path = self.current_recording_path
            saved_folder = self.current_recording_folder
            saved_file = os.path.basename(saved_path) if saved_path else ""

            self.last_saved_path = saved_path
            self.last_saved_folder = saved_folder
            self.current_recording_file = None
            self.current_recording_path = None
            self.is_active = False

            if auto_open and saved_path:
                self.reveal_file(saved_path)

            return {
                "status": "recording_saved",
                "file": saved_file,
                "path": saved_path,
                "folder": saved_folder,
                "size_mb": file_size_mb,
                "bytes": file_size_bytes
            }
        return {"status": "error", "message": "No había archivo de grabación abierto"}

    def reveal_file(self, target_path: str = None) -> dict:
        """Abre el Explorador de Windows seleccionando el archivo grabado o su carpeta."""
        path_to_show = target_path or self.last_saved_path or self.current_recording_folder or self.base_recordings_dir
        norm_path = os.path.normpath(path_to_show)
        is_file = os.path.isfile(norm_path)
        if not is_file:
            os.makedirs(norm_path, exist_ok=True)

        if sys.platform == "win32":
            try:
                if is_file:
                    subprocess.Popen(["explorer.exe", f"/select,{norm_path}"])
                else:
                    os.startfile(norm_path)
            except Exception:
                folder = os.path.dirname(norm_path) if is_file else norm_path
                subprocess.Popen(["explorer.exe", folder])
        return {"status": "ok", "path": norm_path, "is_file": is_file}

    def create_project(self, project_name: str) -> dict:
        """Crea una carpeta de proyecto (grupo de tomas) en el directorio de grabaciones."""
        proj_clean = self._sanitize_name(project_name, "RUTA33")
        folder_path = os.path.join(self.base_recordings_dir, proj_clean)
        os.makedirs(folder_path, exist_ok=True)
        self.current_recording_folder = folder_path
        return {
            "status": "ok",
            "project": proj_clean,
            "folder": os.path.normpath(folder_path)
        }

    def list_projects(self) -> dict:
        """Lista todos los proyectos (grupos de tomas) y sus archivos de video."""
        os.makedirs(self.base_recordings_dir, exist_ok=True)
        default_proj = os.path.join(self.base_recordings_dir, "RUTA33")
        if not os.listdir(self.base_recordings_dir):
            os.makedirs(default_proj, exist_ok=True)

        projects = []
        valid_exts = (".mp4", ".webm", ".mkv", ".mov")
        for entry in sorted(os.listdir(self.base_recordings_dir)):
            full_dir = os.path.join(self.base_recordings_dir, entry)
            if not os.path.isdir(full_dir) or entry.startswith(".") or entry.startswith("Test_"):
                continue

            takes = []
            for root, _, files in os.walk(full_dir):
                for f in sorted(files):
                    if f.lower().endswith(valid_exts):
                        fp = os.path.join(root, f)
                        try:
                            stat = os.stat(fp)
                            takes.append({
                                "name": f,
                                "path": os.path.normpath(fp),
                                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                "bytes": stat.st_size,
                                "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                            })
                        except OSError:
                            pass

            next_num = len(takes) + 1
            projects.append({
                "name": entry,
                "folder": os.path.normpath(full_dir),
                "takes_count": len(takes),
                "next_suggested_take": f"toma{next_num}",
                "takes": takes
            })

        return {
            "status": "ok",
            "base_dir": os.path.normpath(self.base_recordings_dir),
            "projects": projects
        }

    def open_folder(self) -> bool:
        """Abre la carpeta de grabaciones en el Explorador de Windows."""
        folder = self.current_recording_folder or self.last_saved_folder or self.base_recordings_dir
        os.makedirs(folder, exist_ok=True)
        norm_path = os.path.normpath(folder)
        if sys.platform == "win32":
            try:
                os.startfile(norm_path)
                return True
            except Exception:
                subprocess.Popen(["explorer.exe", norm_path])
                return True
        return False
