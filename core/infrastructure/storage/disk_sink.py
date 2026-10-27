"""
Adaptador de infraestructura: Escritura binaria en disco local (SSD/HDD).
Streaming de chunks con flush periódico sin transcodificación pesada.
"""

import os
from typing import Optional
from core.domain.models import TakeSession
from core.domain.exceptions import NoActiveRecordingException

class DiskStorageSink:
    def __init__(self, base_recordings_dir: str):
        self.base_dir = base_recordings_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._current_file = None
        self._current_session: Optional[TakeSession] = None

    @property
    def current_session(self) -> Optional[TakeSession]:
        return self._current_session

    @property
    def current_recording_folder(self) -> Optional[str]:
        return self._current_session.folder_path if self._current_session else None

    def start_take_file(self, session: TakeSession) -> str:
        """Crea la estructura de carpetas y abre el archivo binario para escritura append."""
        os.makedirs(session.folder_path, exist_ok=True)
        
        # Cerrar archivo previo si quedó abierto
        if self._current_file and not self._current_file.closed:
            self._current_file.close()

        self._current_file = open(session.file_path, "wb")
        self._current_session = session
        return session.file_path

    def write_chunk(self, data: bytes) -> int:
        """Escribe un chunk de datos binarios y actualiza el contador de bytes."""
        if not self._current_file or self._current_file.closed or not self._current_session:
            raise NoActiveRecordingException("No hay una sesión de grabación abierta para escribir chunks.")

        self._current_file.write(data)
        self._current_file.flush()
        written = len(data)
        self._current_session.bytes_written += written
        return written

    def seal_take_file(self) -> TakeSession:
        """Sella y cierra el archivo en disco, marcando la sesión como inactiva."""
        if not self._current_file or not self._current_session:
            raise NoActiveRecordingException("No hay una sesión de grabación para sellar.")

        if not self._current_file.closed:
            self._current_file.flush()
            self._current_file.close()

        session = self._current_session
        session.is_active = False
        self._current_file = None
        self._current_session = None
        return session
