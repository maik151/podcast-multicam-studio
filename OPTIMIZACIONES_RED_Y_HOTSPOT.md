# 📶 Manual de Optimizaciones de Red, Hotspot 5GHz y Conectividad Robusta

Este documento detalla las soluciones de ingeniería para resolver el problema clásico de Windows cuando la propia PC emite la Zona con cobertura inalámbrica (Mobile Hotspot), garantizando que los teléfonos siempre alcancen el servidor sin errores de ruteo, firewall o subredes invisibles.

---

## 1. ⚠️ El Problema Común en Windows: ¿Por qué fallan las redes creadas en la PC?

Cuando activas la *"Zona con cobertura inalámbrica móvil"* (Mobile Hotspot) en Windows 10/11:
1. Windows crea un **Adaptador Virtual Oculto** (denominado comúnmente *Microsoft Wi-Fi Direct Virtual Adapter* o *Conexión de área local\* X*).
2. Windows le asigna por defecto la IP de gateway fija **`192.168.137.1`** (a través de Internet Connection Sharing - ICS).
3. **El fallo de las apps comunes:** La mayoría de servidores web programados de forma ingenua consultan `localhost` o toman la primera IP de la tarjeta Ethernet física (ej. `192.168.1.15`). Al generar el código QR con esa IP, los teléfonos conectados al Hotspot (que están en el rango `192.168.137.X`) intentan comunicarse con la red equivocada y la conexión se queda en **timeout infinito**.
4. **El bloqueo de Windows Firewall:** El adaptador virtual a veces entra con perfil "Red Pública", bloqueando puertos entrantes si la app no está configurada correctamente.

---

## 2. 🛡️ Las 5 Soluciones y Optimizaciones Implementadas en el Software

### 1. Enlace Universal en Todas las Interfaces (`0.0.0.0`)
- El servidor HTTPS y WebSocket en Node.js **NUNCA** se enlaza a `localhost` ni a una IP fija.
- Se enlaza estrictamente a `0.0.0.0`:
  ```typescript
  server.listen(8443, '0.0.0.0', () => {
    console.log('Servidor escuchando en todas las interfaces físicas y virtuales');
  });
  ```
- **Efecto:** El servidor escucha simultáneamente en la tarjeta Ethernet, en la tarjeta Wi-Fi física, en el loopback interno y en el adaptador virtual del Hotspot.

### 2. Algoritmo Inteligente de Detección de Gateway (`192.168.137.1`)
- El software analiza todas las tarjetas devueltas por `os.networkInterfaces()`.
- Si detecta que la PC está actuando como Hotspot (presencia de la IP `192.168.137.1` o adaptadores con descripción `Virtual`, `Wi-Fi Direct` o `Hosted Network`):
  - **Prioriza automáticamente esa IP para los códigos QR**.
  - Marca en la pantalla de la PC: `● RED DETECTADA: Zona Wi-Fi 5GHz de la PC (192.168.137.1)`.
  - Los teléfonos escanean el QR y van directamente al gateway nativo sin pasar por puentes inexistentes.

### 3. Certificado SSL Multi-IP con SAN (Subject Alternative Names)
- Tanto Safari (iOS) como Chrome (Android) exigen HTTPS estricto para encender la cámara trasera. Si el certificado SSL no coincide exactamente con la IP del navegador, la cámara se bloquea por seguridad.
- El generador de certificados SSL embebido en la app genera un certificado con **SAN dinámico** que incluye:
  - `DNS:localhost`
  - `IP:127.0.0.1`
  - `IP:192.168.137.1` (IP estándar del Hotspot de Windows)
  - La IP de la red local física actual.
- **Efecto:** Cero pantallas rojas de advertencia de certificado en los teléfonos.

### 4. Protocolo de Handshake con Confirmación Visual ("Ping de Bienvenida")
- En el modal de conexión de la PC, cada slot de cámara tiene un indicador de red interactivo:
  - `CÁMARA 1 (HOST)`: Al escanear el QR, el teléfono hace una petición instantánea `/api/ping`.
  - En la pantalla de la PC el estado cambia a **Verde: "¡Teléfono 1 detectó la PC en 192.168.137.1!"**.
  - Si por alguna razón el teléfono no conecta en 3 segundos, la app ofrece un botón: `[ Cambiar a IP Alternativa ]`.

### 5. Puerto Fijo No Conflictivo (`8443`) y Tráfico UDP Directo
- En lugar de usar puertos comunes que a veces Windows reserva (como el 80 o el 3000), usamos el puerto estándar seguro **`8443`**.
- El transporte de video WebRTC viaja por **UDP local**, el cual fluye sin restricciones en el adaptador virtual de Windows Hotspot, logrando la latencia mínima posible (< 40 ms).

---

## 3. 📋 Matriz de Modos de Red Soportados

| Modo de Red | Quién emite la red | IP asignada a la PC | Comportamiento del Software |
| :--- | :--- | :--- | :--- |
| **Modo 1: Hotspot 5GHz en la PC (Recomendado)** | La PC con Windows 10/11 | `192.168.137.1` | El software detecta la IP `.137.1` y genera los QR con ella. Los teléfonos conectan al gateway. |
| **Modo 2: Hotspot en un Teléfono (iPhone / Android)** | Un teléfono en mesa | `172.20.10.X` (iOS) o `192.168.43.X` (Android) | La PC se conecta al teléfono; el software detecta la nueva IP asignada y actualiza los QR. |
| **Modo 3: Router Dedicado 5GHz / Switch Ethernet** | Router en el set | `192.168.1.X` o `10.0.0.X` | La PC y los teléfonos se conectan al router; el software toma la IP asignada por DHCP. |
| **Modo 4: Cable USB Directo** | Cables USB a la PC | `172.20.10.X` o túnel TCP | El software reconoce el enlace puenteado por USB sin usar Wi-Fi. |
