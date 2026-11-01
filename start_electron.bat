@echo off
title TX-STUDIO // NATIVE ELECTRON BROADCAST SUITE
color 0b
cd /d "%~dp0"

echo =================================================================
echo    TX-STUDIO v1.0.0 // NATIVE FRAMELESS DESKTOP SUITE (ELECTRON)
echo =================================================================
echo.
echo [1/2] Verificando motor de backend Python y Rust Hub...
echo [2/2] Iniciando ventana nativa sin marcos (Frameless Window)...
echo.

if exist "%~dp0dist_electron\win-unpacked\TX-STUDIO Broadcast Suite.exe" (
    start "" "%~dp0dist_electron\win-unpacked\TX-STUDIO Broadcast Suite.exe"
) else (
    cd frontend
    npx electron ../electron/main.js
)
