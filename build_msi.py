"""
Generador de Instalador Nativo Windows (.MSI) para TX-STUDIO v1.0.0.
Utiliza el motor nativo de Windows Installer (COM WindowsInstaller.Installer + makecab.exe)
para producir `dist/TX-Studio-Setup-v1.0.0.msi` sin dependencias externas.

Incluye:
1. Arquitectura de Archivos de Programa (`%LOCALAPPDATA%\\Programs\\TX-Studio\\`).
2. Estructura de Documentos del Usuario (`%USERPROFILE%\\Documents\\TX-STUDIO\\Grabaciones`, `Logs`, `certs`).
3. Desinstalador completo (`uninstall_system.vbs` + `Desinstalar TX-STUDIO.bat` + registro en Windows Settings).
4. Soporte de Actualizaciones Automáticas (`Upgrade` table + `RemoveExistingProducts`) para nuevas versiones.
"""

import os
import sys
import uuid
import shutil
import zipfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DIST_DIR = REPO_ROOT / "dist"
START_STUDIO_DIR = DIST_DIR / "start_studio"
MSI_OUTPUT_PATH = DIST_DIR / "TX-Studio-Setup-v1.0.0.msi"
BUILD_MSI_TMP = REPO_ROOT / "build" / "msi_staging"


def create_app_payload_zip(staging_dir: Path) -> Path:
    """Empaqueta dist/start_studio en un archivo ZIP optimizado para extracción durante la instalación MSI."""
    payload_zip = staging_dir / "tx_studio_bundle.zip"
    print(f"[MSI] Empaquetando distribucion de aplicacion desde {START_STUDIO_DIR}...")
    with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(START_STUDIO_DIR):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(START_STUDIO_DIR)
                zf.write(full_path, rel_path)
    size_mb = payload_zip.stat().st_size / (1024 * 1024)
    print(f"[MSI] Payload de aplicacion generado: {payload_zip.name} ({size_mb:.2f} MB)")
    return payload_zip


def create_post_install_vbs(staging_dir: Path, product_code: str) -> Path:
    """
    Crea el script de configuración de sistema que el MSI ejecuta silenciosamente al instalar:
    1. Descomprime tx_studio_bundle.zip en %LOCALAPPDATA%\\Programs\\TX-Studio
    2. Crea la estructura en Documentos\\TX-STUDIO\\ (Grabaciones, Logs, certs)
    3. Crea el script Desinstalar TX-STUDIO.bat con el ProductCode exacto del MSI
    4. Crea los accesos directos en Escritorio y Menú Inicio con el icono oficial
    """
    vbs_path = staging_dir / "setup_system.vbs"
    vbs_content = f'''On Error Resume Next
Dim fso, shell, installDir, userProfile, docsDir, zipPath, uninstBat
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

installDir = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\\Programs\\TX-Studio")
userProfile = shell.ExpandEnvironmentStrings("%USERPROFILE%")
docsDir = userProfile & "\\Documents\\TX-STUDIO"
zipPath = installDir & "\\tx_studio_bundle.zip"

' 1. Crear estructura de Documentos del Usuario (Grabaciones, Logs, Certs)
If Not fso.FolderExists(docsDir) Then fso.CreateFolder(docsDir)
If Not fso.FolderExists(docsDir & "\\Grabaciones") Then fso.CreateFolder(docsDir & "\\Grabaciones")
If Not fso.FolderExists(docsDir & "\\Logs") Then fso.CreateFolder(docsDir & "\\Logs")
If Not fso.FolderExists(docsDir & "\\certs") Then fso.CreateFolder(docsDir & "\\certs")

' 2. Extraer el paquete de binarios mediante PowerShell nativo sin ventana
Dim psCmd
psCmd = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command ""Expand-Archive -Path '" & zipPath & "' -DestinationPath '" & installDir & "' -Force; Remove-Item -Path '" & zipPath & "' -Force -ErrorAction SilentlyContinue"""
shell.Run psCmd, 0, True

' 3. Generar Desinstalador directo en la carpeta del programa
Set uninstBat = fso.CreateTextFile(installDir & "\\Desinstalar TX-STUDIO.bat", True)
uninstBat.WriteLine "@echo off"
uninstBat.WriteLine "title Desinstalador Oficial // TX-STUDIO Broadcast Suite"
uninstBat.WriteLine "echo Cerrando instancias activas de TX-STUDIO..."
uninstBat.WriteLine "taskkill /F /IM start_studio.exe /T >nul 2>&1"
uninstBat.WriteLine "echo Iniciando desinstalador de Windows Installer..."
uninstBat.WriteLine "msiexec.exe /x {product_code} /qb"
uninstBat.Close

' 4. Crear Acceso Directo en el Escritorio
Dim desktopPath, lnkDesktop
desktopPath = shell.SpecialFolders("Desktop")
Set lnkDesktop = shell.CreateShortcut(desktopPath & "\\TX-STUDIO Broadcast Suite.lnk")
lnkDesktop.TargetPath = installDir & "\\start_studio.exe"
lnkDesktop.WorkingDirectory = installDir
lnkDesktop.IconLocation = installDir & "\\favicon.ico,0"
lnkDesktop.Description = "TX-STUDIO // Professional Multicam Broadcast Suite"
lnkDesktop.Save

' 5. Crear Accesos Directos en el Menú Inicio de Windows (App + Desinstalador)
Dim startMenuPath, lnkStart, lnkUninst
startMenuPath = shell.SpecialFolders("Programs")
Set lnkStart = shell.CreateShortcut(startMenuPath & "\\TX-STUDIO Broadcast Suite.lnk")
lnkStart.TargetPath = installDir & "\\start_studio.exe"
lnkStart.WorkingDirectory = installDir
lnkStart.IconLocation = installDir & "\\favicon.ico,0"
lnkStart.Description = "TX-STUDIO // Professional Multicam Broadcast Suite"
lnkStart.Save

Set lnkUninst = shell.CreateShortcut(startMenuPath & "\\Desinstalar TX-STUDIO.lnk")
lnkUninst.TargetPath = "msiexec.exe"
lnkUninst.Arguments = "/x {product_code}"
lnkUninst.Description = "Desinstalar TX-STUDIO Broadcast Suite del sistema"
lnkUninst.Save

' 6. Crear Acceso Directo a la carpeta de Grabaciones en Documentos\\TX-STUDIO
Dim lnkRecs
Set lnkRecs = shell.CreateShortcut(desktopPath & "\\TX-STUDIO Grabaciones.lnk")
lnkRecs.TargetPath = docsDir & "\\Grabaciones"
lnkRecs.Description = "Grabaciones y Reportes JSON de TX-STUDIO"
lnkRecs.Save
'''
    vbs_path.write_text(vbs_content, encoding="utf-8")
    return vbs_path


def create_uninstall_vbs(staging_dir: Path) -> Path:
    """
    Crea el script de desinstalación limpia que el MSI ejecuta cuando REMOVE="ALL":
    - Cierra start_studio.exe si está abierto.
    - Elimina accesos directos del Escritorio y Menú Inicio.
    - Elimina los binarios extraídos en %LOCALAPPDATA%\\Programs\\TX-Studio.
    - Conserva intactos los videos y logs del usuario en Documentos\\TX-STUDIO.
    """
    vbs_path = staging_dir / "uninstall_system.vbs"
    vbs_content = r'''On Error Resume Next
Dim fso, shell, installDir, desktopPath, startMenuPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

installDir = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\TX-Studio")
desktopPath = shell.SpecialFolders("Desktop")
startMenuPath = shell.SpecialFolders("Programs")

' 1. Detener instancia en ejecución si existe
shell.Run "taskkill.exe /F /IM start_studio.exe /T", 0, True

' 2. Eliminar accesos directos del Escritorio y Menú Inicio
If fso.FileExists(desktopPath & "\TX-STUDIO Broadcast Suite.lnk") Then
    fso.DeleteFile desktopPath & "\TX-STUDIO Broadcast Suite.lnk", True
End If
If fso.FileExists(desktopPath & "\TX-STUDIO Grabaciones.lnk") Then
    fso.DeleteFile desktopPath & "\TX-STUDIO Grabaciones.lnk", True
End If
If fso.FileExists(startMenuPath & "\TX-STUDIO Broadcast Suite.lnk") Then
    fso.DeleteFile startMenuPath & "\TX-STUDIO Broadcast Suite.lnk", True
End If
If fso.FileExists(startMenuPath & "\Desinstalar TX-STUDIO.lnk") Then
    fso.DeleteFile startMenuPath & "\Desinstalar TX-STUDIO.lnk", True
End If

' 3. Limpiar directorio de binarios instalados (conservando Documentos\TX-STUDIO)
Dim psClean
psClean = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command ""Start-Sleep -Milliseconds 600; Remove-Item -Path '" & installDir & "' -Recurse -Force -ErrorAction SilentlyContinue"""
shell.Run psClean, 0, False
'''
    vbs_path.write_text(vbs_content, encoding="utf-8")
    return vbs_path


def create_cabinet_file(staging_dir: Path, files_to_pack: list[tuple[str, Path]]) -> Path:
    """Genera media1.cab usando makecab.exe nativo de Windows."""
    ddf_path = staging_dir / "directives.ddf"
    cab_path = staging_dir / "media1.cab"

    lines = [
        ".OPTION EXPLICIT",
        ".Set CabinetNameTemplate=media1.cab",
        f".Set DiskDirectoryTemplate={staging_dir}",
        ".Set CompressionType=MSZIP",
        ".Set Cabinet=on",
        ".Set Compress=on",
        ".Set MaxDiskSize=0",
    ]
    for file_key, file_path in files_to_pack:
        lines.append(f'"{file_path}" {file_key}')

    ddf_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

    subprocess.run(
        ["makecab.exe", "/F", str(ddf_path)],
        cwd=str(staging_dir),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return cab_path


def generate_msi_database(
    msi_path: Path,
    cab_path: Path,
    files_info: list[tuple[str, str, int]],
    product_code: str
):
    """
    Construye la base de datos relacional Windows Installer (.msi) usando el motor COM
    nativo `WindowsInstaller.Installer` vía VBScript (`cscript.exe`), embebiendo `media1.cab`,
    configurando soporte de actualización (`Upgrade` table) y desinstalador automático.
    """
    if msi_path.exists():
        msi_path.unlink()

    package_code = "{" + str(uuid.uuid4()).upper() + "}"
    upgrade_code = "{8A7F4D12-5C3E-4B9A-9D1E-2F6B8C4A1001}"
    comp_guid = "{" + str(uuid.uuid4()).upper() + "}"

    vbs_builder = BUILD_MSI_TMP / "create_msi.vbs"

    sql_statements = [
        "CREATE TABLE `Property` (`Property` CHAR(72) NOT NULL, `Value` LONGCHAR NOT NULL PRIMARY KEY `Property`)",
        "CREATE TABLE `Directory` (`Directory` CHAR(72) NOT NULL, `Directory_Parent` CHAR(72), `DefaultDir` CHAR(255) NOT NULL PRIMARY KEY `Directory`)",
        "CREATE TABLE `Component` (`Component` CHAR(72) NOT NULL, `ComponentId` CHAR(38), `Directory_` CHAR(72) NOT NULL, `Attributes` SHORT NOT NULL, `Condition` CHAR(255), `KeyPath` CHAR(72) PRIMARY KEY `Component`)",
        "CREATE TABLE `Feature` (`Feature` CHAR(38) NOT NULL, `Feature_Parent` CHAR(38), `Title` CHAR(64), `Description` CHAR(255), `Display` SHORT, `Level` SHORT NOT NULL, `Directory_` CHAR(72), `Attributes` SHORT NOT NULL PRIMARY KEY `Feature`)",
        "CREATE TABLE `FeatureComponents` (`Feature_` CHAR(38) NOT NULL, `Component_` CHAR(72) NOT NULL PRIMARY KEY `Feature_`, `Component_`)",
        "CREATE TABLE `File` (`File` CHAR(72) NOT NULL, `Component_` CHAR(72) NOT NULL, `FileName` CHAR(255) NOT NULL, `FileSize` LONG NOT NULL, `Version` CHAR(72), `Language` CHAR(20), `Attributes` SHORT, `Sequence` SHORT NOT NULL PRIMARY KEY `File`)",
        "CREATE TABLE `Media` (`DiskId` SHORT NOT NULL, `LastSequence` SHORT NOT NULL, `DiskPrompt` CHAR(64), `Cabinet` CHAR(255), `VolumeLabel` CHAR(32), `Source` CHAR(72) PRIMARY KEY `DiskId`)",
        "CREATE TABLE `CustomAction` (`Action` CHAR(72) NOT NULL, `Type` SHORT NOT NULL, `Source` CHAR(72), `Target` CHAR(255) PRIMARY KEY `Action`)",
        "CREATE TABLE `InstallExecuteSequence` (`Action` CHAR(72) NOT NULL, `Condition` CHAR(255), `Sequence` SHORT PRIMARY KEY `Action`)",
        "CREATE TABLE `InstallUISequence` (`Action` CHAR(72) NOT NULL, `Condition` CHAR(255), `Sequence` SHORT PRIMARY KEY `Action`)",
        "CREATE TABLE `Registry` (`Registry` CHAR(72) NOT NULL, `Root` SHORT NOT NULL, `Key` CHAR(255) NOT NULL, `Name` CHAR(255), `Value` LONGCHAR, `Component_` CHAR(72) NOT NULL PRIMARY KEY `Registry`)",
        "CREATE TABLE `Upgrade` (`UpgradeCode` CHAR(38) NOT NULL, `VersionMin` CHAR(20), `VersionMax` CHAR(20), `Language` CHAR(20), `Attributes` LONG NOT NULL, `Remove` CHAR(255), `ActionProperty` CHAR(72) NOT NULL PRIMARY KEY `UpgradeCode`, `VersionMin`, `VersionMax`, `Language`, `Attributes`)",
        f"INSERT INTO `Property` (`Property`, `Value`) VALUES ('ProductCode', '{product_code}')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('ProductName', 'TX-STUDIO Broadcast Suite')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('ProductVersion', '1.0.0')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('Manufacturer', 'TX-STUDIO Broadcast Engineering')",
        f"INSERT INTO `Property` (`Property`, `Value`) VALUES ('UpgradeCode', '{upgrade_code}')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('ProductLanguage', '1033')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('MSIINSTALLPERUSER', '1')",
        "INSERT INTO `Property` (`Property`, `Value`) VALUES ('SECURECUSTOMPROPERTIES', 'OLDPRODUCTS')",
        f"INSERT INTO `Upgrade` (`UpgradeCode`, `VersionMin`, `VersionMax`, `Attributes`, `ActionProperty`) VALUES ('{upgrade_code}', '0.0.1', '1.0.0', 257, 'OLDPRODUCTS')",
        "INSERT INTO `Directory` (`Directory`, `DefaultDir`) VALUES ('TARGETDIR', 'SourceDir')",
        "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('LocalAppDataFolder', 'TARGETDIR', '.')",
        "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('ProgramsDir', 'LocalAppDataFolder', 'Programs')",
        "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('INSTALLDIR', 'ProgramsDir', 'TX-Stu~1|TX-Studio')",
        f"INSERT INTO `Component` (`Component`, `ComponentId`, `Directory_`, `Attributes`, `KeyPath`) VALUES ('MainComponent', '{comp_guid}', 'INSTALLDIR', 4, 'RegKeyPath')",
        r"INSERT INTO `Registry` (`Registry`, `Root`, `Key`, `Name`, `Value`, `Component_`) VALUES ('RegKeyPath', 1, 'Software\TX-Studio', 'InstallPath', '[INSTALLDIR]', 'MainComponent')",
        "INSERT INTO `Feature` (`Feature`, `Title`, `Description`, `Display`, `Level`, `Directory_`, `Attributes`) VALUES ('MainFeature', 'TX-STUDIO Core Engine', 'Motor Multicam WebRTC y Consola de Direccion', 1, 1, 'INSTALLDIR', 0)",
        "INSERT INTO `FeatureComponents` (`Feature_`, `Component_`) VALUES ('MainFeature', 'MainComponent')",
    ]

    seq = 1
    for file_key, file_name, file_size in files_info:
        sql_statements.append(
            f"INSERT INTO `File` (`File`, `Component_`, `FileName`, `FileSize`, `Attributes`, `Sequence`) "
            f"VALUES ('{file_key}', 'MainComponent', '{file_name}', {file_size}, 512, {seq})"
        )
        seq += 1

    sql_statements.extend([
        f"INSERT INTO `Media` (`DiskId`, `LastSequence`, `Cabinet`, `VolumeLabel`) VALUES (1, {len(files_info)}, '#media1.cab', 'DISK1')",
        "INSERT INTO `CustomAction` (`Action`, `Type`, `Source`, `Target`) VALUES ('RunSystemSetup', 1122, 'INSTALLDIR', 'wscript.exe //B \"[INSTALLDIR]setup_system.vbs\"')",
        "INSERT INTO `CustomAction` (`Action`, `Type`, `Source`, `Target`) VALUES ('RunSystemUninstall', 1122, 'INSTALLDIR', 'wscript.exe //B \"[INSTALLDIR]uninstall_system.vbs\"')",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('FindRelatedProducts', 50)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('LaunchConditions', 100)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('CostInitialize', 800)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('FileCost', 900)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('CostFinalize', 1000)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('InstallValidate', 1400)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('InstallInitialize', 1500)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('RemoveExistingProducts', 1550)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('ProcessComponents', 1600)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('UnpublishFeatures', 1800)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Condition`, `Sequence`) VALUES ('RunSystemUninstall', 'REMOVE=\"ALL\"', 2500)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('RemoveRegistryValues', 2600)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('RemoveFiles', 3500)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('CreateFolders', 3700)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('InstallFiles', 4000)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('WriteRegistryValues', 5000)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('RegisterUser', 6000)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('RegisterProduct', 6100)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('PublishFeatures', 6300)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('PublishProduct', 6400)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Condition`, `Sequence`) VALUES ('RunSystemSetup', 'NOT Installed', 6500)",
        "INSERT INTO `InstallExecuteSequence` (`Action`, `Sequence`) VALUES ('InstallFinalize', 6600)",
    ])

    vbs_exec_lines = []
    for stmt in sql_statements:
        escaped = stmt.replace('"', '""')
        vbs_exec_lines.append(f'ExecSql db, "{escaped}"')

    vbs_code = f'''Option Explicit
Sub ExecSql(db, sql)
    Dim view
    Set view = db.OpenView(sql)
    view.Execute
    view.Close
End Sub

Dim installer, db, viewStream, recordStream, sumInfo
Set installer = CreateObject("WindowsInstaller.Installer")
Set db = installer.OpenDatabase("{str(msi_path)}", 3)

{chr(10).join(vbs_exec_lines)}

' Embeber media1.cab en la tabla _Streams
Set viewStream = db.OpenView("INSERT INTO `_Streams` (`Name`, `Data`) VALUES ('media1.cab', ?)")
Set recordStream = installer.CreateRecord(1)
recordStream.SetStream 1, "{str(cab_path)}"
viewStream.Execute recordStream
viewStream.Close

' Summary Information Stream
Set sumInfo = db.SummaryInformation(20)
sumInfo.Property(1) = 1252
sumInfo.Property(2) = "Installation Database"
sumInfo.Property(3) = "TX-STUDIO Broadcast Suite v1.0.0"
sumInfo.Property(4) = "TX-STUDIO Broadcast Engineering"
sumInfo.Property(5) = "Installer"
sumInfo.Property(6) = "Instalador oficial de sistema para TX-STUDIO Multicam Broadcast Suite"
sumInfo.Property(7) = "Intel;1033"
sumInfo.Property(9) = "{package_code}"
sumInfo.Property(14) = 200
sumInfo.Property(15) = 2
sumInfo.Property(18) = "Windows Installer"
sumInfo.Persist

db.Commit
WScript.Echo "[MSI] Base de datos MSI generada exitosamente."
'''
    vbs_builder.write_text(vbs_code, encoding="utf-8")

    subprocess.run(
        ["cscript.exe", "//Nologo", str(vbs_builder)],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def build_msi():
    """Flujo completo de construcción de `dist/TX-Studio-Setup-v1.0.0.msi`."""
    if not START_STUDIO_DIR.exists():
        raise FileNotFoundError(f"No se encontro {START_STUDIO_DIR}. Ejecuta primero PyInstaller.")

    if BUILD_MSI_TMP.exists():
        shutil.rmtree(BUILD_MSI_TMP, ignore_errors=True)
    BUILD_MSI_TMP.mkdir(parents=True, exist_ok=True)

    product_code = "{" + str(uuid.uuid4()).upper() + "}"

    # 1. Crear ZIP de payload + scripts de instalación/desinstalación + icono
    payload_zip = create_app_payload_zip(BUILD_MSI_TMP)
    setup_vbs = create_post_install_vbs(BUILD_MSI_TMP, product_code)
    uninst_vbs = create_uninstall_vbs(BUILD_MSI_TMP)
    favicon_src = REPO_ROOT / "favicon.ico"
    favicon_dst = BUILD_MSI_TMP / "favicon.ico"
    shutil.copy2(favicon_src, favicon_dst)

    files_to_pack = [
        ("FilePayloadZip", payload_zip),
        ("FileSetupVbs", setup_vbs),
        ("FileUninstVbs", uninst_vbs),
        ("FileFaviconIco", favicon_dst),
    ]

    # 2. Compilar media1.cab
    cab_path = create_cabinet_file(BUILD_MSI_TMP, files_to_pack)

    # 3. Información para tabla File (formato 8.3 | LongFileName)
    files_info = [
        ("FilePayloadZip", "txbundle.zip|tx_studio_bundle.zip", payload_zip.stat().st_size),
        ("FileSetupVbs", "setupsys.vbs|setup_system.vbs", setup_vbs.stat().st_size),
        ("FileUninstVbs", "uninstsy.vbs|uninstall_system.vbs", uninst_vbs.stat().st_size),
        ("FileFaviconIco", "favicon.ico|favicon.ico", favicon_dst.stat().st_size),
    ]

    # 4. Generar archivo .MSI final
    generate_msi_database(MSI_OUTPUT_PATH, cab_path, files_info, product_code)
    msi_mb = MSI_OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"[MSI] [OK] Instalador Windows MSI listo: {MSI_OUTPUT_PATH} ({msi_mb:.2f} MB)")


if __name__ == "__main__":
    build_msi()
