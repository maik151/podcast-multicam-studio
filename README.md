# 🎙️ TX-STUDIO // Professional Multicam Broadcast Suite (v1.0.0)

Sistema autónomo de producción, conmutación multicámara en tiempo real (60 FPS) y grabación Master para podcasts, operando **100% en red local (LAN / Wi-Fi 5GHz / Hotspot)** con teléfonos iOS y Android como cámaras inalámbricas WebRTC P2P de ultra-baja latencia.

---

## ✨ Características Principales

- **📡 Matriz Multicámara Inalámbrica WebRTC (P2P LAN):**
  - Emparejamiento instantáneo por código QR para hasta 3 cámaras móviles (`CAM 01 HOST`, `CAM 02 GUEST`, `CAM 03 WIDE`).
  - Des-ofuscación automática de candidatos ICE `.local` (mDNS) y selección inteligente de la ruta física Wi-Fi/Ethernet (descartando adaptadores virtuales VMware/VirtualBox/WSL).
  - Control remoto desde la consola del Director: cambio de lente (`0.5x`, `1.0x`, `2.0x`), activación de linterna (`FLASH`), luz Tally en vivo (`ON-AIR` rojo / `PREVIEW` verde) y modo de ahorro térmico **OLED**.
- **🎬 Compositor Master 60 FPS y Switcher Broadcast (`Hardware Takeover`):**
  - Conmutación por teclado sin latencia: `[1]`, `[2]`, `[3]` para corte directo, clic derecho para armar en `PREVIEW`, `[SPACE]` para `AUTO MIX` (disolvencia suave), `DIP [D]` (Dip to Black cinemático de 600ms), `BLACK OUT [B]` y **T-Bar Virtual** interactivo.
  - Guías de encuadre profesionales en lienzo (`[G]`): `SAFE AREA 80% (SMPTE 259M)`, recorte vertical `TIKTOK / REELS 9:16` y `REGLA DE TERCIOS`.
- **🎚️ Procesador de Audio DSP en Tiempo Real (`Web Audio API`):**
  - Osciloscopio de fósforo ámbar en vivo y vúmetros estéreo de 16 segmentos LED (`RMS`, `PEAK`, `LUFS`).
  - Cadena de procesamiento vocal: Compresor dinámico (`COMP ON`), Filtro pasa-altos 80Hz (`LOW-CUT 80`), Saturación analógica (`TAPE WARM`) y compensación de sincronización labial (`LIP SYNC 0–300ms` / `TAP SYNC [T]`).
- **🔴 Grabación Master Tolerante a Fallos y Banderas CUE:**
  - Escritura progresiva por fragmentos (`chunked streaming`) directamente a disco en `Documentos\TX-STUDIO\Grabaciones\`.
  - Inserción de marcadores de edición en caliente (`REC FLAG [R]`) exportados automáticamente a hojas de corte `.json` junto al video.
- **📊 Matriz de Trazabilidad Total y Diagnóstico en JSON (`Logs/`):**
  - Registro unificado de eventos de Backend, Frontend Director y Cámaras Móviles en `Documentos\TX-STUDIO\Logs\`:
    - `tx_studio_events.jsonl` (trazabilidad cronológica milimétrica).
    - `latest_session.json` (resumen matricial por nivel, categoría y componente).
    - `error_matrix.json` (catálogo automático de incidentes indicando exactamente archivo, línea, función y causa raíz).
- **🧭 Tutorial Interactivo Integrado (`? TUTORIAL`):**
  - Guía paso a paso con iluminación dinámica de zonas para entrenar a nuevos operadores en segundos.

---

## 📦 Arquitectura de Sistema Windows e Instalación (`.MSI`)

El proyecto incluye un generador nativo de instaladores Windows (`build_msi.py`) y empaquetado GUI sin ventana de consola (`start_studio.spec`):

1. **Instalador Oficial de Sistema (`dist/TX-Studio-Setup-v1.0.0.msi`):**
   - Instala los binarios autónomos en `%LOCALAPPDATA%\Programs\TX-Studio\`.
   - Crea los accesos directos en el **Escritorio** y **Menú Inicio** con el isotipo oficial de TX-STUDIO.
   - Registra el certificado raíz X.509 v3 en el almacén de confianza de Windows (`CurrentUser\Root`) para evitar advertencias HTTPS.
   - Crea la estructura de usuario en `C:\Users\<Usuario>\Documents\TX-STUDIO\` (`Grabaciones\`, `Logs\`, `certs\`).
   - Incluye **Desinstalador oficial** en Configuración de Windows y soporte de **Actualización Automática (`MajorUpgrade`)**.
2. **Ejecutable Único Portable (`dist/TX-Studio-v1.0.0-Portable.exe`):**
   - Versión *single-file* lista para ejecutar sin instalación.

---

## 🛠️ Desarrollo y Compilación Desde el Código Fuente

### Requisitos
- **Python 3.11+** (entorno virtual `.venv`)
- **Node.js 20+ / Angular CLI 19** (`frontend/`)

### Comandos Principales

```powershell
# 1. Ejecutar suite completa de pruebas automatizadas (68 tests)
.\.venv\Scripts\python.exe -m unittest test_sprint0 test_sprint1 test_sprint2 test_sprint3 test_sprint4 test_sprint5 test_angular test_backend_clean_arch

# 2. Compilar el Frontend Angular 19
cd frontend
npm run build
cd ..

# 3. Empaquetar Ejecutables GUI (.exe) y generar el Instalador Windows (.MSI)
.\.venv\Scripts\pyinstaller.exe --noconfirm start_studio.spec
.\.venv\Scripts\python.exe build_msi.py
```
