@echo off
title TX-STUDIO v1.0.0 // Professional Broadcast Suite
color 0b
cd /d "%~dp0"

echo =================================================================
echo        TX-STUDIO v1.0.0 // PROFESSIONAL BROADCAST SUITE
echo =================================================================
echo.
echo [FIREWALL] Verificando reglas de red para WebRTC y HTTPS (Puerto 8443)...
powershell -NoProfile -Command "if (-not (Get-NetFirewallRule -DisplayName 'TXStudio_HTTPS_8443' -ErrorAction SilentlyContinue)) { try { New-NetFirewallRule -DisplayName 'TXStudio_HTTPS_8443' -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow -ErrorAction Stop | Out-Null; New-NetFirewallRule -DisplayName 'TXStudio_WebRTC_UDP' -Direction Inbound -Protocol UDP -Action Allow -ErrorAction Stop | Out-Null; Write-Output '[FIREWALL] Reglas TCP/UDP para WebRTC creadas exitosamente.' } catch { Write-Output '[FIREWALL] Ejecutando con permisos de usuario estandar.' } } else { Write-Output '[FIREWALL] Reglas TCP/UDP verificadas.' }"

echo.
echo [INICIANDO] Abriendo consola de direccion y servidor de transmision...
echo.

if exist "%~dp0dist\start_studio\start_studio.exe" (
    "%~dp0dist\start_studio\start_studio.exe" %*
) else if exist "%~dp0dist\TX-Studio-v1.0.0-Portable.exe" (
    "%~dp0dist\TX-Studio-v1.0.0-Portable.exe" %*
) else (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
)

echo.
echo =================================================================
echo El servidor se ha detenido.
echo =================================================================
pause
