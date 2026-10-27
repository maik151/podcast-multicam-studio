# 📋 Especificación de Requerimientos: Podcast Multicam Studio

- **Proyecto:** Podcast Multicam Studio (Software Autónomo de Switcher Multicámara & Grabación)
- **Ruta del Proyecto:** `c:\Proyects\GITHUB_REPOS\Proyects_repo\podcast_multicam_studio\`
- **Versión:** 1.0.0-SPEC
- **Metodología:** Spec-Driven Development (`sdd-skill`) + Shape Up (`shaping-skills`)
- **Apetito:** Ciclo de Desarrollo enfocado en MVP funcional de alta estabilidad.

---

## 1. Declaración del Problema & Objetivo
### El Problema
Los sistemas actuales (DroidCam / Wi-Fi doméstico / plugins DirectShow) provocan colapso de red inalámbrica, pantallas blancas por conflicto de hooks en Windows, sobrecalentamiento de teléfonos y dependencia de interfaces saturadas que distraen durante la grabación de un podcast.

### El Objetivo
Construir una **aplicación de escritorio nativa e independiente (sin requerir OBS Studio)** que:
1. Actúe como consola central de grabación y dirección para podcasts.
2. Ingeste concurrentemente 3 teléfonos inteligentes (iOS y Android) como cámaras por WebRTC local (Wi-Fi 5GHz o cable USB).
3. Permita alternar cámaras en tiempo real con atajos de teclado (`1`, `2`, `3`) aplicando transiciones fluidas (Corte, Disolvencia/Fade).
4. Capture el audio de estudio directamente desde la interfaz XLR/USB de la PC y lo grabe sincronizado con el video final en un archivo local MP4/MKV.

---

## 2. Requerimientos Funcionales (RF)

### RF-01: Ingesta de Video Multidispositivo (iOS & Android)
- **RF-01.1**: El sistema servirá una PWA/Web ligera mediante HTTPS local accesible desde Safari (iOS) y Chrome (Android).
- **RF-01.2**: Emparejamiento instantáneo mediante código QR para cada slot de cámara (`Cámara 1`, `Cámara 2`, `Cámara 3`).
- **RF-01.3**: Selección de lente trasera (Principal 1x o Gran Angular 0.5x).
- **RF-01.4**: Prevención de bloqueo de pantalla (*Screen Wake Lock API*).
- **RF-01.5**: Modo Ahorro Térmico (pantalla OLED en negro con brillo mínimo para evitar *thermal throttling* en podcasts largos).
- **RF-01.6**: Luz Tally en el teléfono (borde verde = Preview, borde rojo brillante = En Vivo / Program).

### RF-02: Consola de Escritorio Nativa (PC Director)
- **RF-02.1**: Ventana de escritorio centralizada empaquetada con **Electron**.
- **RF-02.2**: Vista Multiview de 4 cuadrantes:
  - 3 monitores pequeños con la señal en vivo de cada cámara y su estado de conexión.
  - 1 monitor principal (**Program Out**) con la señal final que se está grabando.
- **RF-02.3**: Monitoreo de nivel de audio (Vúmetro estéreo en vivo) de la interfaz de sonido de la PC.
- **RF-02.4**: Botón maestro de **GRABAR TOMA** con contador de tiempo transcurrido (HH:MM:SS) y estado de escritura a disco.
- **RF-02.5**: **Canal de Monitoreo por Auriculares para el Director**: El operador puede escuchar en tiempo real a través de los auriculares de la PC la mezcla de audio final con deslizador de volumen de monitoreo y botón de Mute CUE.

### RF-03: Motor de Switching y Transiciones
- **RF-03.1**: Cambio de cámara instantáneo mediante teclado numérico o teclas principales:
  - `1`: Cámara 1
  - `2`: Cámara 2
  - `3`: Cámara 3
- **RF-03.2**: Modos de transición configurables:
  - **Corte Directo (Cut)**: Cambio instantáneo a 0 ms.
  - **Disolvencia Cruzada (Crossfade / Mix)**: Interpolación suave programable (ej. 250 ms a 400 ms).
- **RF-03.3**: Mezclador de video ejecutado sobre **WebGL 2.0 / Canvas** acelerado por la GPU de la PC.

### RF-04: Captura y Sincronización de Audio
- **RF-04.1**: Selección de la fuente de entrada de audio de la PC (interfaz USB/XLR como Focusrite, Rodecaster, Shure, etc.).
- **RF-04.2**: Buffer de sincronización de audio (Sync Offset ajustable en milisegundos de 0 a 300 ms) para alinear perfectamente los labios del video WebRTC con la voz del micrófono.
- **RF-04.3**: **Matriz de Ruteo de Audio**: Selector para elegir entre micrófono de estudio (PC), audio de celulares individuales o modo *Audio-Follows-Video (AFV)*.

### RF-05: Grabación y Codificación a Disco
- **RF-05.1**: Codificación acelerada por hardware (Nvidia NVENC / Intel QuickSync / AMD AMF o MediaRecorder de Chromium).
- **RF-05.2**: Exportación directa a archivo `.mp4` o `.mkv` en la carpeta configurada del proyecto.
- **RF-05.3**: Mecanismo de persistencia segura: si se cierra la app abruptamente, el archivo no debe quedar corrupto (fragmented MP4 o MKV).
- **RF-05.4**: Resolución bloqueada en **1080p Full HD (1920x1080)** con bitrate configurable (8.000 a 12.000 kbps).
- **RF-05.5**: **Sistema de Múltiples Tomas (Take Chunking)**: Cada pausa o corte genera un nuevo archivo numerado (`Episodio_Toma_01.mp4`, `Episodio_Toma_02.mp4`) sin interrumpir la sesión ni la conexión de las cámaras.
- **RF-05.6**: **Grabación ISO Multicámara Opcional**: Interruptor en ajustes para habilitar la grabación independiente de las 3 cámaras en simultáneo si la tarjeta gráfica dispone de potencia suficiente.

---

## 3. Requerimientos No Funcionales (RNF)

- **RNF-01 (Latencia)**: Latencia de transporte video local < 120 ms entre el movimiento físico frente al teléfono y la pantalla del director.
- **RNF-02 (Rendimiento PC)**: Uso de CPU < 25% en PCs modernas gracias a decodificación y renderizado por GPU (WebGL + NVENC).
- **RNF-03 (Red Aislada y Optimización para 5GHz / Hotspot Móvil)**:
  - **Cero dependencia de internet:** El sistema opera en modo *Offline Puro*. La negociación WebRTC utiliza únicamente candidatos ICE locales de tipo `host` (UDP directo), eliminando la necesidad de servidores STUN o TURN externos.
  - **Soporte de Punto de Acceso 5GHz (Windows Hotspot o Celular):** El software detecta automáticamente si la PC está emitiendo una Zona Wi-Fi en 5GHz o si está conectada al Hotspot de un teléfono (rango `192.168.137.X`, `172.20.10.X`, etc.), autogenerando los códigos QR con la IP exacta de esa subred.
  - **Alineación de Bitrate para 5GHz:** Cada cámara transmite con un tope optimizado de 8 Mbps (24 Mbps en total), ocupando menos del 10% del ancho de banda real de un canal 5GHz (300 a 867 Mbps), evitando la contención de paquetes y el jitter.
- **RNF-04 (Autonomía Móvil)**: Los teléfonos deben poder operar continuamente al menos 90 minutos sin apagarse por sobrecalentamiento gracias al modo OLED.

---

## 4. Casos Borde y Mitigación de Fallos

| Caso Borde | Comportamiento del Sistema |
| :--- | :--- |
| **Pérdida de señal de un teléfono (ej. batería agotada)** | El monitor de esa cámara en la consola muestra un aviso "Cámara Desconectada" con fondo oscuro. Si esa cámara estaba "En Vivo", el sistema salta automáticamente a la cámara restante o a un plano de emergencia sin congelar la grabación. |
| **Reconexión durante la grabación** | Al recargar la página del teléfono, se renegocia la sesión WebRTC y el video vuelve a la consola sin necesidad de reiniciar la app ni detener la grabación. |
| **Desfase progresivo de audio/video (Drift)** | El reloj de composición de WebGL se vincula a las marcas de tiempo (`timestamps`) de presentación del flujo de audio del sistema operativo. |

---

## 5. Lo que Explícitamente NO Haremos en el MVP (No-Gos)
- ❌ No habrá streaming hacia YouTube/Twitch (es exclusivamente para **grabación de podcast local en alta fidelidad**).
- ❌ No habrá edición post-grabación no lineal (la app entrega el archivo master ya switcheado).
- ❌ No se usarán servicios en la nube de pago ni servidores de señalización externos. Todo corre en la máquina local.

---

## 6. Criterio de Aceptación (Definition of Done)
1. Abrir la app `.exe` en la PC y ver el panel Multiview.
2. Conectar simultáneamente 1 iPhone y 1 Android escaneando los QR.
3. Conectar el micrófono USB de la PC y verificar modulación en el vúmetro.
4. Presionar `GRABAR`, presionar las teclas `1`, `2`, `3` alternando las tomas con transiciones fluidas.
5. Detener la grabación y reproducir el archivo final `.mp4` con sincronía perfecta de audio y video a 1080p.
