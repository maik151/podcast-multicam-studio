# -*- mode: python ; coding: utf-8 -*-
"""
Especificación PyInstaller para Podcast Multicam Studio (TX-STUDIO v1.0.0).
Genera:
1. Distribución de directorio rápida: dist/start_studio/start_studio.exe
2. Ejecutable Único Portable para GitHub Releases: dist/TX-Studio-v1.0.0-Portable.exe
"""

import sys
import os

block_cipher = None

BASE_DIR = os.path.abspath(os.curdir)

a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=[
        ('frontend/dist/frontend/browser', 'frontend/dist/frontend/browser'),
        ('static', 'static'),
        ('tools/platform-tools', 'tools/platform-tools'),
        ('favicon.ico', '.'),
    ],
    hiddenimports=[
        'aiohttp',
        'aiohttp.web',
        'aiohttp.web_urldispatcher',
        'aiohttp.web_fileresponse',
        'cryptography',
        'cryptography.x509',
        'cryptography.hazmat.primitives.asymmetric.rsa',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.primitives.serialization',
        'qrcode',
        'qrcode.image.svg',
        'core',
        'core.config',
        'core.domain.models',
        'core.domain.exceptions',
        'core.recording.recorder_service',
        'core.recording.markers_service',
        'core.signaling.hub',
        'core.signaling.webrtc_router',
        'core.telemetry.system_telemetry',
        'core.network.connection_manager',
        'core.network.detector',
        'core.infrastructure.network',
        'core.infrastructure.desktop_launcher',
        'core.infrastructure.json_logger',
        'core.presentation.app_factory',
        'core.presentation.controllers.network_controller',
        'core.presentation.controllers.recording_controller',
        'core.presentation.controllers.signaling_controller',
        'core.presentation.controllers.spa_controller',
        'core.presentation.controllers.telemetry_controller',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'unittest', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 1. Ejecutable para carpeta dist/start_studio/start_studio.exe (Arranque instantáneo GUI sin consola negra)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='start_studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/public/favicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='start_studio',
)

# 2. Ejecutable Único Portable (Single-File .exe GUI sin consola negra para GitHub Releases / Distribución Directa)
exe_portable = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TX-Studio-v1.0.0-Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/public/favicon.ico',
)
