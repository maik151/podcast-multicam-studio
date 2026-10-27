"""
Módulo de telemetría de hardware de Windows (CPU, RAM, Espacio en Disco).
Utiliza llamadas nativas ctypes de la API de Windows para cero sobrecarga.
"""

import sys
import os
import shutil
import ctypes

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]

_last_cpu_time = 0
_last_idle_time = 0

def get_system_telemetry(recordings_dir: str) -> dict:
    """Obtiene uso real de RAM, CPU y espacio libre en disco en Windows."""
    # 1. RAM (GlobalMemoryStatusEx)
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_ram = round(stat.ullTotalPhys / (1024**3), 1)
    used_ram = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1)
    ram_load = stat.dwMemoryLoad

    # 2. CPU (GetSystemTimes)
    global _last_cpu_time, _last_idle_time
    idle = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
    def to_int(ft): return (ft.dwHighDateTime << 32) + ft.dwLowDateTime
    cur_idle = to_int(idle)
    cur_total = to_int(kernel) + to_int(user)
    
    cpu_percent = 0.0
    if _last_cpu_time > 0 and cur_total > _last_cpu_time:
        total_diff = cur_total - _last_cpu_time
        idle_diff = cur_idle - _last_idle_time
        cpu_percent = max(0.0, min(100.0, round((1.0 - (idle_diff / total_diff)) * 100, 1)))
    _last_cpu_time = cur_total
    _last_idle_time = cur_idle

    # 3. Disco
    disk_target = recordings_dir if os.path.exists(recordings_dir) else os.path.dirname(recordings_dir)
    total_disk, used_disk, free_disk = shutil.disk_usage(disk_target)
    free_disk_gb = round(free_disk / (1024**3), 1)
    total_disk_gb = round(total_disk / (1024**3), 1)
    disk_percent = round((used_disk / total_disk) * 100, 1)

    return {
        "cpu_percent": cpu_percent,
        "ram_used_gb": used_ram,
        "ram_total_gb": total_ram,
        "ram_percent": ram_load,
        "disk_free_gb": free_disk_gb,
        "disk_total_gb": total_disk_gb,
        "disk_percent": disk_percent,
        "disk_warning": free_disk_gb < 15.0
    }
