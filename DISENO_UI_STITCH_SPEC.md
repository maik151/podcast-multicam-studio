# 🎨 Especificación de Diseño UI/UX para Stitch: Podcast Multicam Studio

Documento rector de diseño visual, sistema de tokens, referencias estéticas (Dribbble / Pinterest / Broadcast) y prompts estructurados para la generación de pantallas mediante **Stitch**.

---

## 1. 🎯 La Dirección de Arte & Estilo Visual

Para evitar que Stitch genere dashboards genéricos con gráficos pastel o tarjetas de e-commerce, definimos una dirección estética estricta:

- **Concepto:** **Professional Broadcast Dark Console / High-End Audio Engineering**
- **Inspiración:**
  - *Blackmagic Design ATEM Software Control*
  - *DaVinci Resolve (Fairlight Audio Console)*
  - *Roland Pro A/V Video Switchers*
  - *Elgato Wave Link & Stream Deck*
  - *Teenage Engineering* (precisión minimalista, diales limpios, tipografía técnica)
- **Filosofía Ergonómica:**
  - **Cero fatiga visual:** Fondo grafito oscuro mate, no negro puro agresivo.
  - **Semántica de Broadcast:** El rojo **SOLO** se usa para `ON AIR` (Grabando / En Vivo). El verde **SOLO** se usa para `PREVIEW` (Siguiente toma) y audio en nivel seguro.
  - **Contraste de alta legibilidad:** Números de timecode y decibeles en tipografía monoespaciada para lectura instantánea en un set de grabación tenue.

---

## 2. 🎨 Paleta de Color & Tokens de Diseño

```css
/* Fondos y Superficies */
--bg-app: #0b0d10;         /* Fondo base profundo */
--bg-surface: #14171d;     /* Paneles y tarjetas de monitores */
--bg-surface-elevated: #1c212a; /* Botones inactivos y toolbars */
--border-subtle: #262c37;  /* Separadores delgados de 1px */

/* Semántica de Estudio (Tally Lights) */
--tally-program-red: #ef4444;   /* EN VIVO / AL AIRE (Glow intenso) */
--tally-preview-green: #22c55e; /* PREVIO / LISTO */
--tally-standby: #475569;       /* Espera / Standby */

/* Acentos y Controles */
--accent-cyan: #06b6d4;         /* Selección activa de audio y sliders */
--accent-orange: #f59e0b;       /* Advertencias y audio próximo a clipping */

/* Audio VU Meter Gradients */
--vu-safe: #10b981;    /* -60 dB a -12 dB (Verde) */
--vu-warning: #f59e0b; /* -12 dB a -3 dB (Amarillo/Ámbar) */
--vu-clip: #ef4444;    /* > -3 dB a 0 dB (Rojo peak) */

/* Tipografía */
--font-ui: "Inter", -apple-system, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", monospace;
```

---

## 3. 🖥️ Las 3 Pantallas Mapeadas para Stitch

### 📺 Pantalla 1: Consola de Dirección Principal (Desktop)
*La vista operativa del director técnico del podcast durante la grabación.*

- **Top Bar (Barra Superior de Producción):**
  - Indicador `REC` con punto rojo pulsante, timecode en tipografía monoespaciada grande (`01:24:18`).
  - Indicador de estado de disco: `● GRABANDO EN NVENC (MP4) | 480 GB Libres`.
  - Medidor de recursos discreto: `CPU 12% | GPU 24% | 60 FPS`.
  - Botón modal `[ 📱 Conectar Cámaras (QR) ]`.
- **Área Central (Matriz de Video):**
  - **Fila Superior (3 Monitores Pequeños - Entradas de Teléfonos):**
    - `CAM 1: HOST (iPhone 14 Pro)` | Borde Tally Verde/Rojo | Badge `1080p 60fps` | `Latencia 48ms` | `Batería 88%`.
    - `CAM 2: INVITADO 1 (Galaxy S22)` | Borde Tally Standby | Badge `1080p 60fps` | `Latencia 52ms` | `Batería 74%`.
    - `CAM 3: PLANO GENERAL (iPhone 12)` | Borde Tally Standby | Badge `1080p 60fps` | `Latencia 41ms` | `Batería 92%`.
  - **Fila Inferior Izquierda (Monitor PROGRAM - Master Out):**
    - Pantalla grande 16:9 con marco rojo brillante y badge superior `PROGRAM LIVE`.
- **Panel de Control Inferior (Switcher & Transiciones):**
  - Botones táctiles grandes tipo broadcast:
    - `[ 1 ] HOST` (Atajo Tecla 1)
    - `[ 2 ] INVITADO` (Atajo Tecla 2)
    - `[ 3 ] GENERAL` (Atajo Tecla 3)
  - Botones de transición:
    - `[ CORTE (CUT) ]` (Inmediato)
    - `[ FADE 300ms ]` (Disolvencia suave)
    - Slider de velocidad de transición (`100ms - 800ms`).
- **Lateral Derecho (Matriz de Audio & Vúmetros):**
  - Vúmetros digitales verticales estéreo de alta resolución (-60 a 0 dB).
  - Selector de fuente activa:
    - `(•) Micrófono PC (Focusrite Scarlett 2i2 XLR)`
    - `( ) Micrófono Celular 1`
    - `( ) Audio Follows Video (AFV)`
  - Control rotativo / slider de compensación labial: `Lip-Sync Delay: +85 ms`.

---

### 📱 Pantalla 2: Interfaz Móvil PWA (iOS Safari & Android Chrome)
*La pantalla que ve el teléfono montado en el trípode.*

- **Modo 1: Visor de Cámara Activo:**
  - Vista previa de la cámara trasera a pantalla completa en 1080p.
  - Marco perimetral **Tally ultra visible a distancia**:
    - Borde rojo brillante de 8px cuando está `ON AIR`.
    - Borde verde cuando está en `PREVIEW`.
    - Borde gris tenue cuando está en espera.
  - Píldora flotante superior: `Slot: CÁMARA 1 (HOST)` | `Resolución: 1080p60` | `Estado: Enlazado`.
  - Controles inferiores táctiles:
    - Selector de lente: `[ 0.5x Gran Angular ]` `[ 1x Principal ]` `[ 2x Tele ]`.
    - Toggle de micrófono: `[ 🎙️ Enviar Audio Celular: ON/OFF ]`.
    - Bloqueo de enfoque y exposición: `[ 🔒 Lock AF/AE ]`.
    - Botón maestro de ahorro: `[ 🌙 Activar Modo OLED ]`.
- **Modo 2: Modo Ahorro Térmico (OLED Black Mode):**
  - Pantalla 98% en negro puro `#000000`.
  - Únicamente una barra horizontal superior delgada (roja o verde) indicando el estado Tally y un reloj tenue, reduciendo al 0% el calor emitido por la pantalla durante 2 horas de podcast.

---

### 🪟 Pantalla 3: Modal de Emparejamiento Rápido QR (Desktop)
*La ventana emergente que abre el director para conectar los 3 teléfonos en 10 segundos.*

- 3 tarjetas elegantes lado a lado:
  - **Tarjeta 1: Cámara 1 (Host)**: Código QR nítido, enlace `https://192.168.1.15:8443/cam/1`, botón copiar enlace.
  - **Tarjeta 2: Cámara 2 (Invitado)**: Código QR nítido, enlace `https://192.168.1.15:8443/cam/2`.
  - **Tarjeta 3: Cámara 3 (Plano General)**: Código QR nítido, enlace `https://192.168.1.15:8443/cam/3`.
- Instrucciones breves: *"1. Conecta el teléfono al Wi-Fi del estudio. 2. Abre la cámara y escanea el código. 3. Toca 'Permitir cámara' en el navegador."*

---

## 4. 🤖 Prompts de Alta Precisión Listos para StitchMCP

### Prompt para Pantalla 1 (Desktop Console):
> `"Professional broadcast video switcher and podcast recording desktop application UI in deep dark graphite theme (#0b0d10, #14171d). Layout: Top production bar with a pulsing red REC indicator, digital mono timecode (01:24:18), hardware NVENC MP4 indicator, 480GB disk space meter, and 'Connect Cameras (QR)' button. Center-left: Multiview 16:9 grid showing 3 camera preview monitors (Cam 1 Host, Cam 2 Guest, Cam 3 Wide) with green/red Tally borders, 1080p 60fps badges, 45ms latency, and battery indicators. Below them is a large master PROGRAM output monitor with a glowing red 'ON AIR' badge. Bottom-center: tactile switcher panel with large broadcast pushbuttons '[ 1 ] HOST', '[ 2 ] GUEST', '[ 3 ] WIDE', and transition buttons '[ CUT ]', '[ FADE 300ms ]'. Right sidebar: precision audio console with dual vertical stereo LED VU meters (-60dB to 0dB with green-yellow-red gradient), master audio source selector dropdown for 'PC USB Interface (Focusrite XLR)' vs mobile mics, audio gain sliders, and a Lip-Sync delay slider (+85ms). Clean, technical aesthetic inspired by Blackmagic ATEM and DaVinci Resolve."`

### Prompt para Pantalla 2 (Mobile PWA):
> `"Mobile camera operator PWA interface for live podcast streaming in dark studio aesthetic. Fullscreen 1080p camera viewfinder framed with an ultra-visible glowing 8px Tally border (Crimson Red for ON AIR). Top floating translucent pill displaying 'CAM 1: HOST', '1080p 60fps', and 'LAN Connected'. Bottom minimalist glassmorphism controls: pill selector for camera lenses '[ 0.5x ] [ 1x ] [ 2x ]', a microphone toggle button '[ 🎙️ Send Phone Mic ]', autofocus lock toggle '[ 🔒 Lock AF ]', and an prominent '🌙 OLED Thermal Saver' button. High-contrast typography, ergonomic for tripod mounting in a studio set."`

### Prompt para Pantalla 3 (Modal QR Pairing):
> `"Desktop modal window for quick camera pairing in a podcast studio software. Sleek matte dark card with 3 columns for Cam 1 (Host), Cam 2 (Guest), and Cam 3 (Wide Angle). Each column displays a high-contrast QR code, local secure URL (https://192.168.1.X:8443/cam/1), camera status pill ('Waiting for connection...'), and a 'Copy Link' button. Bottom instructions in clean subtle typography: '1. Connect to Studio Wi-Fi. 2. Scan QR with iOS Safari or Android Chrome. 3. Tap Allow Camera'. Minimalist broadcast style."`
