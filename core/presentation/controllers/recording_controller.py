"""
Controlador HTTP de Grabación y Marcadores (Presentation Layer).
"""

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
            project=data.get("project", "Podcast"),
            episode=data.get("episode", "Episodio_01"),
            take=int(data.get("take", 1)),
            resolution=data.get("resolution", "1080p"),
            fps=int(data.get("fps", 60)),
            ext=data.get("ext", "webm"),
            custom_name=data.get("customName", "")
        )
        return web.json_response(res)

    async def handle_chunk(self, request: web.Request) -> web.Response:
        chunk = await request.read()
        res = self.recorder.write_chunk(chunk)
        return web.json_response(res)

    async def handle_stop(self, request: web.Request) -> web.Response:
        res = self.recorder.stop_take()
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
        folder = self.recorder.current_recording_folder or self.recorder.base_recordings_dir
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{folder}"')
        return web.json_response({"status": "ok", "folder": folder})
