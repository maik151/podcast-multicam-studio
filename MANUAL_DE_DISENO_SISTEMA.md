# 🎨 Sistema de Diseño Oficial: TX-STUDIO
### *Estética: Teenage Engineering (OP-1 / TX-6) + Pixel Hardware Broadcast*

---

## 1. 🏷️ Identidad de Marca y Logo
* **Nombre Oficial:** **`TX-STUDIO`**
* **Insignia Visual:** Isotipo **`TX`** en relieve isométrico tridimensional pixel-art con chasis oscuro redondeado.
* **Logotipo:** Tipografía bitmap / pixelada de 8 bits en bloque de alto contraste (`#ffffff` / `#000000` con detalles sombreados).
* **Asset Oficial:** `/logo-tx-studio.png`

---

## 2. 🔤 Tipografía Oficial (Pixel & Technical Stack)

| Familia | Tipo | Uso en la Aplicación |
| :--- | :--- | :--- |
| **`Silkscreen`** | **Pixel / 8-Bit Hardware** | **Rótulos de Keycaps (`CAM 01 HOST [1]`), títulos de buses, estados Tally (`● ON AIR`, `PREVIEW`) y botones de acción.** Idéntica a la pantalla OLED de sintetizadores analógicos. |
| **`Pixelify Sans`** | **Pixel Moderno** | **Títulos grandes y encabezados secundarios.** |
| **`JetBrains Mono`** | **Monoespaciada Técnica** | **Timecode continuo, valores numéricos en dBFS, porcentajes de latencia y telemetría de red/sistema.** Garantiza que los números no oscilen horizontalmente al refrescar a 60 FPS. |
| **`Space Grotesk`** | **Industrial Suiza** | **Textos de lectura extendida en diálogos y modales.** |

---

## 3. 🕹️ Iconografía Pixel-Art (`Pixelarticons`)

Utilizamos la librería oficial **`Pixelarticons`** para mantener coherencia pixel-perfect de 24x24 con la estética retro-digital:

* `pia-camera`: Identificador de slots de cámaras celulares.
* `pia-volume-2` / `pia-volume-x`: Estado de audio master y retardo.
* `pia-sliders`: Panel de ecualización y potenciómetros.
* `pia-zap`: Alimentación y carga rápida de smartphones.
* `pia-radio-tower`: Enlace WebRTC P2P activo.
* `pia-folder`: Explorador de grabaciones físicas en SSD.
* `pia-flag`: Marcadores de clips destacados para Shorts / Reels (`REC FLAG [R]`).

---

## 4. 🎨 Paleta Cromática (Teenage Engineering Hardware)

| Token | Código Hex | Semántica y Función |
| :--- | :--- | :--- |
| **`--primary`** | `#ff6200` | **Electric Safety Amber (OP-1):** Selección activa, borde TALLY Program, vúmetro superior. |
| **`--secondary`** | `#ffb68b` | **Soft Peach / Amber:** TALLY Preview, previsualización, advertencias de nivel. |
| **`--surface-lowest`** | `#0e0703` | Cavidad profunda del osciloscopio vectorial y sliders. |
| **`--surface`** | `#111318` | Chasis principal oscuro anti-reflejo. |
| **`--surface-panel`** | `#1a1c20` | Tarjetas modulares de cámaras y docks. |
| **`--error / rec`** | `#ff3b30` | **Broadcast Red:** Indicador exclusivo de grabación en disco activa y clipping digital. |
| **`--safe`** | `#10b981` | Conexión segura WebRTC y nivel nominal de diálogo (-60 a -12 dBFS). |

---

## 5. 🎛️ Componentes Físicos Táctiles (Tactile Hardware)

* **Keycaps Físicas:** Botones tipo tecla mecánica de switch broadcast con reborde sutil, etiquetas en `Silkscreen` y atajos en `JetBrains Mono` entre corchetes (`[1]`, `[2]`, `[3]`, `[SPACE]`, `[B]`, `[M]`, `[H]`, `[T]`).
* **Tally Lights:** Bordes perimetrales con resplandor difuso (`tally-program`: `#ff6200` con glow ámbar; `tally-preview`: `#ffb68b`).
* **Potenciómetros:** Canaletas empotradas con indicadores de escala milimétrica en dB y milisegundos.
