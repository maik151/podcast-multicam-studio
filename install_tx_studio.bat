@echo off
title Instalador Oficial // TX-STUDIO v1.0.0 Broadcast Suite
color 0e
cd /d "%~dp0"

echo =====================================================================
echo      INSTALADOR DE WINDOWS // TX-STUDIO v1.0.0 BROADCAST SUITE
echo =====================================================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\TX-Studio"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\TX-STUDIO Broadcast Suite.lnk"
set "STARTMENU_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\TX-STUDIO Broadcast Suite.lnk"

if not exist "%~dp0dist\start_studio\start_studio.exe" (
    echo [ERROR] No se encontro el paquete compilado en dist\start_studio\start_studio.exe
    echo Ejecuta primero el build o descomprime el paquete completo.
    pause
    exit /b 1
)

echo [1/4] Creando directorio de instalacion en:
echo       %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [2/4] Copiando binarios autonomos, motor WebRTC y assets de marca...
xcopy "%~dp0dist\start_studio\*" "%INSTALL_DIR%\" /E /I /Y /Q >nul
if exist "%~dp0favicon.ico" copy /Y "%~dp0favicon.ico" "%INSTALL_DIR%\favicon.ico" >nul

echo [3/4] Configurando reglas de Firewall de Windows (HTTPS 8443 y UDP WebRTC)...
powershell -NoProfile -Command "try { New-NetFirewallRule -DisplayName 'TXStudio_HTTPS_8443' -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow -ErrorAction Stop | Out-Null; New-NetFirewallRule -DisplayName 'TXStudio_WebRTC_UDP' -Direction Inbound -Protocol UDP -Action Allow -ErrorAction Stop | Out-Null; Write-Output '      Reglas de Firewall configuradas.' } catch { Write-Output '      Aviso: Para configurar Firewall por primera vez, ejecuta como Administrador.' }"

echo [4/4] Creando accesos directos en Escritorio y Menu Inicio con icono oficial...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s1 = $ws.CreateShortcut('%DESKTOP_LNK%'); $s1.TargetPath = '%INSTALL_DIR%\start_studio.exe'; $s1.WorkingDirectory = '%INSTALL_DIR%'; $s1.IconLocation = '%INSTALL_DIR%\favicon.ico'; $s1.Description = 'TX-STUDIO Professional Broadcast Suite'; $s1.Save(); $s2 = $ws.CreateShortcut('%STARTMENU_LNK%'); $s2.TargetPath = '%INSTALL_DIR%\start_studio.exe'; $s2.WorkingDirectory = '%INSTALL_DIR%'; $s2.IconLocation = '%INSTALL_DIR%\favicon.ico'; $s2.Description = 'TX-STUDIO Professional Broadcast Suite'; $s2.Save();"

echo.
echo =====================================================================
echo  ✅ INSTALACION COMPLETADA EXITOSAMENTE (TX-STUDIO v1.0.0)
echo =====================================================================
echo  - Ruta instalada:  %INSTALL_DIR%
echo  - Acceso directo:  Escritorio ("TX-STUDIO Broadcast Suite")
echo  - Menu Inicio:     TX-STUDIO Broadcast Suite
echo =====================================================================
echo.
set /p LAUNCH="¿Deseas iniciar TX-STUDIO ahora mismo? (S/N): "
if /i "%LAUNCH%"=="S" (
    start "" "%INSTALL_DIR%\start_studio.exe"
)
