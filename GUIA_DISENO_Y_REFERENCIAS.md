# 🎨 Guía de Diseño, Referencias Visuales y Anatomía de Pantallas

Documento de referencia para el diseño manual (en Figma, Stitch Web o herramientas de UI/UX) del sistema **Podcast Multicam Studio**.

---

## 1. 🔍 Referencias Visuales y Estéticas

### A. Referencias del Mundo Real (Hardware y Software Profesional)
1. **Blackmagic ATEM Software Control / ATEM Mini Pro**:
   - Referencia dorada en switchers de broadcast.
   - Botones retroiluminados táctiles con retroalimentación clara de **Preview (Verde)** y **Program (Rojo)**.
   - Disposición en barra de buses de video y transiciones dedicadas (`CUT` y `AUTO`).
2. **Elgato Wave Link & Stream Deck**:
   - El estándar moderno de software de audio para podcasters y streamers.
   - Vúmetros LED verticales multicanal, deslizadores limpios y selectores de mute y ganancia.
3. **Teenage Engineering (TX-6 Field Mixer & OP-1)**:
   - Estética industrial minimalista técnica.
   - Tipografía monoespaciada de alta precisión, controles rotativos limpios y fondos grafito oscuro mate.

### B. Búsquedas Recomendadas en Dribbble / Pinterest / Behance
- `"Broadcast switcher UI dark mode"`
- `"Live stream control room interface"`
- `"Audio mixer dashboard dark theme"`
- `"Camera monitor UI tally light"`
- `"DAW mixer channel strip minimalist"`

---

## 2. 📐 Anatomía de Pantallas a Diseñar

### Pantalla 1: Consola de Dirección Desktop (1920x1080)
- **TopBar de Producción:**
  - Botón maestro `REC` con punto pulsante.
  - Reloj Timecode digital monoespaciado (`00:00:00`).
  - Monitor de almacenamiento (`SSD: 420 GB Libres`).
  - Botón modal `[ 📱 Conectar Cámaras (QR) ]`.
- **Matriz de Video Multivista:**
  - 3 mini-monitores 16:9 (`CAM 1 HOST`, `CAM 2 INVITADO`, `CAM 3 GENERAL`) con bordes Tally de estado (Rojo/Verde/Gris), resolución `1080p60`, latencia en ms e indicador de batería.
  - 1 monitor maestro `PROGRAM LIVE` en grande con badge `ON AIR`.
- **Botonera de Switcher:**
  - Botones de selección rápida: `[ 1 ] HOST`, `[ 2 ] INVITADO`, `[ 3 ] GENERAL`.
  - Botones de transición: `[ CORTE (CUT) ]`, `[ DISOLVENCIA (FADE) ]` con slider de velocidad (100ms - 800ms).
- **Módulo Mezclador de Audio:**
  - Vúmetros LED verticales estéreo (-60dB a 0dB con colores verde, amarillo y rojo peak).
  - Selector de fuente: Micrófono PC (interfaz XLR) vs Micrófonos de celulares vs Audio Follows Video (AFV).
  - Slider de calibración labial: `Lip-Sync Delay (+85 ms)`.

### Pantalla 2: Interfaz Móvil para el Operador (PWA iOS & Android)
- **Modo Visor Normal:**
  - Visor 1080p a pantalla completa.
  - **Borde Tally Perimetral de 8px:** Rojo brillante cuando está al aire, Verde en previo, Gris en espera.
  - Controles flotantes: Selector de lentes (`0.5x`, `1x`, `2x`), toggle de micrófono del celular (`ON/OFF`), botón de bloqueo `[ 🔒 Lock AF/AE ]`.
  - Botón destacado: `[ 🌙 Modo Ahorro OLED ]`.
- **Modo Ahorro Térmico (OLED Black Mode):**
  - Pantalla 99% negra pura para apagar los píxeles y enfriar el teléfono en podcasts largos.
  - Línea superior delgada con indicador Tally y reloj tenue.

### Pantalla 3: Modal de Emparejamiento Rápido QR
- 3 tarjetas con códigos QR grandes para escanear en 5 segundos con el teléfono y asignar automáticamente las cámaras 1, 2 y 3.
