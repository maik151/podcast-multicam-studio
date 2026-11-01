"""
Controlador HTTP de Grabación y Marcadores (Presentation Layer).
"""

import os
import sys
import subprocess
from aiohttp import web
from core.application import RecorderService, MarkersService

class RecordingController:
    def __init__(self, recorder_service: RecorderService, markers_service: MarkersService):
        self.recorder = recorder_service
        self.markers = markers_service

    async def handle_start(self, request: web.Request) -> web.Response:
        data = await request.json()
        res = self.recorder.start_take(
            project=data.get("project", "RUTA33"),
            episode=data.get("episode", "Episodio_01"),
            take=int(data.get("take", 1)),
            resolution=data.get("resolution", "1080p"),
            fps=int(data.get("fps", 60)),
            ext=data.get("ext", "mp4"),
            custom_name=data.get("customName", "") or data.get("takeName", "")
        )
        return web.json_response(res)

    async def handle_chunk(self, request: web.Request) -> web.Response:
        chunk = await request.read()
        res = self.recorder.write_chunk(chunk)
        return web.json_response(res)

    async def handle_stop(self, request: web.Request) -> web.Response:
        auto_open = True
        try:
            if request.can_read_body:
                body = await request.json()
                if isinstance(body, dict) and "autoOpen" in body:
                    auto_open = bool(body["autoOpen"])
        except Exception:
            pass
        res = self.recorder.stop_take(auto_open=auto_open)
        return web.json_response(res)

    async def handle_list_projects(self, request: web.Request) -> web.Response:
        res = self.recorder.list_projects()
        return web.json_response(res)

    async def handle_create_project(self, request: web.Request) -> web.Response:
        data = await request.json()
        project_name = data.get("project", "RUTA33")
        res = self.recorder.create_project(project_name)
        return web.json_response(res)

    async def handle_reveal(self, request: web.Request) -> web.Response:
        target_path = None
        try:
            if request.can_read_body:
                data = await request.json()
                target_path = data.get("path")
        except Exception:
            pass
        res = self.recorder.reveal_file(target_path)
        return web.json_response(res)

    async def handle_marker(self, request: web.Request) -> web.Response:
        data = await request.json()
        res = self.markers.add_marker(
            project=data.get("project", "Podcast"),
            episode=data.get("episode", "Episodio_01"),
            take=int(data.get("take", 1)),
            timecode_str=data.get("timecode", "00:00:00"),
            note=data.get("note", "Clip destacado"),
            count=data.get("count", 1),
            current_folder=self.recorder.current_recording_folder
        )
        return web.json_response(res)

    async def handle_open_folder(self, request: web.Request) -> web.Response:
        try:
            folder = self.recorder.current_recording_folder or self.recorder.base_recordings_dir
            os.makedirs(folder, exist_ok=True)
            norm_path = os.path.normpath(folder)
            if sys.platform == "win32":
                try:
                    os.startfile(norm_path)
                except Exception:
                    subprocess.Popen(["explorer.exe", norm_path])
            return web.json_response({"status": "ok", "folder": norm_path})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)
