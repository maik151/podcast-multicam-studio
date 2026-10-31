use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::logger;
use crate::slot::CameraSlot;
use crate::usbmuxd;

const SOI: [u8; 2] = [0xFF, 0xD8];
const EOI: [u8; 2] = [0xFF, 0xD9];

/// Inicia el hilo en segundo plano que vigila y captura el flujo de video de una cámara.
pub fn start_ingest_worker(slot: Arc<CameraSlot>) {
    thread::Builder::new()
        .name(format!("ingest-cam-{}", slot.id))
        .spawn(move || {
            logger::info(&format!("INGEST-{}", slot.id), "Hilo de ingesta de video iniciado");

            loop {
                slot.force_reconnect.store(false, Ordering::SeqCst);
                let platform = slot.get_platform();
                let target_port = slot.get_port();
                let device_id = slot.get_device_id();

                let stream_opt = if platform == "ios" {
                    let dev_id = device_id.unwrap_or_else(|| usbmuxd::get_first_iphone_id().unwrap_or(3));
                    // Conectar a DroidCam en iPhone (puerto estándar 4747 primero)
                    usbmuxd::connect_iphone_port(dev_id, 4747)
                        .or_else(|| usbmuxd::connect_iphone_port(dev_id, 4748))
                } else {
                    TcpStream::connect_timeout(
                        &format!("127.0.0.1:{}", target_port).parse().unwrap(),
                        Duration::from_millis(600),
                    ).ok()
                };

                match stream_opt {
                    Some(mut stream) => {
                        logger::info(
                            &format!("INGEST-{}", slot.id),
                            &format!("Conexión establecida con {} en puerto {}", platform, target_port)
                        );

                        let _ = stream.set_read_timeout(Some(Duration::from_millis(3000)));
                        let _ = stream.set_write_timeout(Some(Duration::from_millis(1500)));

                        let req = b"GET /video HTTP/1.0\r\nHost: 127.0.0.1\r\nUser-Agent: TX-Studio-Hub\r\nAccept: multipart/x-mixed-replace, image/jpeg, */*\r\nConnection: close\r\n\r\n";
                        if let Err(e) = stream.write_all(req) {
                            logger::warn(&format!("INGEST-{}", slot.id), &format!("Fallo al enviar handshake: {}", e));
                            slot.set_disconnected();
                            thread::sleep(Duration::from_millis(500));
                            continue;
                        }

                        let mut read_buf = [0u8; 65536];
                        let mut frame_buf = Vec::with_capacity(262144);
                        let mut frames_received = 0u64;

                        loop {
                            if slot.force_reconnect.load(Ordering::SeqCst) {
                                logger::info(&format!("INGEST-{}", slot.id), "Reconfiguración solicitada, reiniciando túnel...");
                                break;
                            }

                            match stream.read(&mut read_buf) {
                                Ok(0) => {
                                    logger::warn(&format!("INGEST-{}", slot.id), "Stream cerrado por el dispositivo");
                                    break;
                                }
                                Ok(n) => {
                                    frame_buf.extend_from_slice(&read_buf[..n]);

                                    while let Some(soi_pos) = find_subsequence(&frame_buf, &SOI) {
                                        if soi_pos > 0 {
                                            frame_buf.drain(..soi_pos);
                                        }

                                        if let Some(eoi_pos) = find_subsequence(&frame_buf[2..], &EOI) {
                                            let full_eoi_pos = 2 + eoi_pos + 1;
                                            let frame_data = frame_buf[..=full_eoi_pos].to_vec();
                                            
                                            slot.push_frame(frame_data);
                                            frames_received += 1;
                                            if frames_received == 1 {
                                                logger::info(
                                                    &format!("INGEST-{}", slot.id),
                                                    "Primer fotograma JPEG recibido correctamente (Stream LIVE)"
                                                );
                                            }

                                            frame_buf.drain(..=full_eoi_pos);
                                        } else {
                                            break;
                                        }
                                    }

                                    if frame_buf.len() > 10 * 1024 * 1024 {
                                        frame_buf.clear();
                                    }
                                }
                                Err(e) => {
                                    logger::warn(&format!("INGEST-{}", slot.id), &format!("Timeout o desconexión física de socket: {}", e));
                                    break;
                                }
                            }
                        }

                        slot.set_disconnected();
                        if frames_received == 0 {
                            thread::sleep(Duration::from_millis(1200));
                        }
                    }
                    None => {
                        slot.set_disconnected();
                    }
                }

                thread::sleep(Duration::from_millis(400));
            }
        })
        .expect("Fallo al crear hilo de ingesta");
}

fn find_subsequence(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|window| window == needle)
}
