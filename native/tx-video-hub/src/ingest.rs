use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::slot::CameraSlot;
use crate::usbmuxd;

const SOI: [u8; 2] = [0xFF, 0xD8];
const EOI: [u8; 2] = [0xFF, 0xD9];

/// Inicia el hilo en segundo plano que vigila y captura el flujo de video de una cámara.
pub fn start_ingest_worker(slot: Arc<CameraSlot>) {
    thread::Builder::new()
        .name(format!("ingest-cam-{}", slot.id))
        .spawn(move || {
            loop {
                let platform = slot.get_platform();
                let target_port = slot.get_port();

                let stream_opt = if platform == "ios" {
                    // Soporte para iPhone vía usbmuxd
                    let dev_id = usbmuxd::get_first_iphone_id().unwrap_or(1);
                    // Probar primero el puerto de DroidCam OBS (4748), luego el clásico (4747)
                    usbmuxd::connect_iphone_port(dev_id, 4748)
                        .or_else(|| usbmuxd::connect_iphone_port(dev_id, 4747))
                } else {
                    // Soporte para Android vía ADB forward (127.0.0.1:puerto)
                    TcpStream::connect_timeout(
                        &format!("127.0.0.1:{}", target_port).parse().unwrap(),
                        Duration::from_millis(600),
                    ).ok()
                };

                match stream_opt {
                    Some(mut stream) => {
                        let _ = stream.set_read_timeout(Some(Duration::from_millis(3000)));
                        let _ = stream.set_write_timeout(Some(Duration::from_millis(1500)));

                        // Solicitar el flujo de video HTTP MJPEG a DroidCam
                        let req = b"GET /video HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
                        if stream.write_all(req).is_err() {
                            slot.set_disconnected();
                            thread::sleep(Duration::from_millis(500));
                            continue;
                        }

                        // Parsear tramas JPEG continuamente
                        let mut read_buf = [0u8; 65536];
                        let mut frame_buf = Vec::with_capacity(262144); // 256 KB buffer inicial

                        loop {
                            match stream.read(&mut read_buf) {
                                Ok(0) => {
                                    // Conexión cerrada por el teléfono
                                    break;
                                }
                                Ok(n) => {
                                    frame_buf.extend_from_slice(&read_buf[..n]);

                                    // Buscar delimitadores de imagen JPEG completos
                                    while let Some(soi_pos) = find_subsequence(&frame_buf, &SOI) {
                                        if soi_pos > 0 {
                                            // Descartar bytes residuales antes del inicio de imagen
                                            frame_buf.drain(..soi_pos);
                                        }

                                        // Buscar el final de la imagen a partir del SOI
                                        if let Some(eoi_pos) = find_subsequence(&frame_buf[2..], &EOI) {
                                            let full_eoi_pos = 2 + eoi_pos + 1; // índice inclusivo del byte 0xD9
                                            let frame_data = frame_buf[..=full_eoi_pos].to_vec();
                                            
                                            // Enviar el fotograma completado al slot (Zero Latency)
                                            slot.push_frame(frame_data);

                                            // Limpiar el fotograma consumido del búfer
                                            frame_buf.drain(..=full_eoi_pos);
                                        } else {
                                            // Aún no llega el EOI completo, esperar la próxima lectura
                                            break;
                                        }
                                    }

                                    // Prevenir fugas de memoria si los datos vinieran corruptos
                                    if frame_buf.len() > 10 * 1024 * 1024 {
                                        frame_buf.clear();
                                    }
                                }
                                Err(_) => {
                                    // Timeout o error de red en el cable USB
                                    break;
                                }
                            }
                        }

                        slot.set_disconnected();
                    }
                    None => {
                        slot.set_disconnected();
                    }
                }

                // Esperar antes del siguiente intento de reconexión automática
                thread::sleep(Duration::from_millis(500));
            }
        })
        .expect("Fallo al crear hilo de ingesta");
}

fn find_subsequence(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|window| window == needle)
}
