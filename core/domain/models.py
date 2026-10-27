"""
Entidades y modelos del dominio puro para Podcast Multicam Studio.
No dependen de ningún framework web ni infraestructura externa.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class VideoProfile:
    id: str
    width: int
    height: int
    fps: int
    name: str

@dataclass
class TakeSession:
    project: str
    episode: str
    take: int
    resolution: str
    fps: int
    extension: str
    file_path: str
    folder_path: str
    started_at: datetime = field(default_factory=datetime.now)
    bytes_written: int = 0
    is_active: bool = True

@dataclass
class MarkerFlag:
    index: int
    timecode: str
    note: str
    created_at: str

@dataclass(frozen=True)
class SystemTelemetryData:
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_free_gb: float
    cpu_percent: float

@dataclass(frozen=True)
class NetworkInterfaceInfo:
    ip: str
    type_name: str
    base_url: str
