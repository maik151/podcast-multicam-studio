use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::slot::CameraSlot;

pub const HTTP_PORT: u16 = 9100;

/// Inicia el servidor HTTP multihilo de streaming en el puerto 9100.
pub fn start_http_server(slots: Arc<Vec<Arc<CameraSlot>>>) {
    let listener = TcpListener::bind(format!("127.0.0.1:{}", HTTP_PORT))
        .expect("Fallo al enlazar puerto 9100 para tx-video-hub");

    println!("[tx-video-hub] Servidor de video nativo activo en http://127.0.0.1:{}", HTTP_PORT);

    thread::Builder::new()
        .name("http-server".to_string())
        .spawn(move || {
            for stream in listener.incoming() {
                if let Ok(mut stream) = stream {
                    let slots_clone = Arc::clone(&slots);
                    thread::spawn(move || {
                        handle_client(&mut stream, &slots_clone);
                    });
                }
            }
        })
        .expect("Fallo al iniciar hilo del servidor HTTP");
}

fn handle_client(stream: &mut TcpStream, slots: &[Arc<CameraSlot>]) {
    let _ = stream.set_read_timeout(Some(Duration::from_millis(3000)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(4000)));

    let mut buf = [0u8; 1024];
    let n = match stream.read(&mut buf) {
        Ok(n) if n > 0 => n,
        _ => return,
    };

    let req_str = String::from_utf8_lossy(&buf[..n]);
    let mut lines = req_str.lines();
    let request_line = match lines.next() {
        Some(line) => line,
        None => return,
    };

    let parts: Vec<&str> = request_line.split_whitespace().collect();
    if parts.len() < 2 {
        return;
    }

    let method = parts[0];
    let path = parts[1];

    if method == "OPTIONS" {
        let resp = concat!(
            "HTTP/1.1 204 No Content\r\n",
            "Access-Control-Allow-Origin: *\r\n",
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n",
            "Access-Control-Allow-Headers: Content-Type\r\n",
            "Content-Length: 0\r\n",
            "\r\n"
        );
        let _ = stream.write_all(resp.as_bytes());
        return;
    }

    if path == "/status" {
        let mut cam_json = String::new();
        for (i, slot) in slots.iter().enumerate() {
            let fps = (slot.fps_x10.load(Ordering::Relaxed) as f64) / 10.0;
            let conn = slot.is_connected.load(Ordering::Relaxed);
            let port = slot.get_port();
            let plat = slot.get_platform();
            if i > 0 {
                cam_json.push_str(", ");
            }
            cam_json.push_str(&format!(
                "\"{}\": {{\"connected\": {}, \"fps\": {:.1}, \"port\": {}, \"platform\": \"{}\"}}",
                slot.id, conn, fps, port, plat
            ));
        }

        let body = format!("{{\"status\": \"ok\", \"hub\": \"tx-video-hub\", \"cameras\": {{{}}}}}", cam_json);
        let resp = format!(
            concat!(
                "HTTP/1.1 200 OK\r\n",
                "Content-Type: application/json\r\n",
                "Access-Control-Allow-Origin: *\r\n",
                "Cache-Control: no-cache\r\n",
                "Content-Length: {}\r\n",
                "\r\n",
                "{}"
            ),
            body.len(),
            body
        );
        let _ = stream.write_all(resp.as_bytes());
        return;
    }

    // Ruta: /feed/1, /feed/2, /feed/3
    if path.starts_with("/feed/") {
        let id_str = path.trim_start_matches("/feed/").split('?').next().unwrap_or("1");
        let cam_id: usize = id_str.parse().unwrap_or(1);

        let slot = match slots.iter().find(|s| s.id == cam_id) {
            Some(s) => s,
            None => {
                let not_found = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n";
                let _ = stream.write_all(not_found.as_bytes());
                return;
            }
        };

        // Enviar encabezado Multipart MJPEG de ultra-baja latencia
        let header = concat!(
            "HTTP/1.1 200 OK\r\n",
            "Content-Type: multipart/x-mixed-replace; boundary=--txframe\r\n",
            "Cache-Control: no-cache, no-store, must-revalidate\r\n",
            "Pragma: no-cache\r\n",
            "Access-Control-Allow-Origin: *\r\n",
            "Connection: close\r\n",
            "\r\n"
        );

        if stream.write_all(header.as_bytes()).is_err() {
            return;
        }

        let mut last_seq: u64 = 0;

        loop {
            let mut guard = slot.latest_frame.lock().unwrap();

            // Esperar el siguiente fotograma disponible
            while slot.frame_seq.load(Ordering::SeqCst) == last_seq {
                let res = slot.condvar.wait_timeout(guard, Duration::from_millis(200)).unwrap();
                guard = res.0;
                if res.1.timed_out() {
                    // Si no hay cámara activa, salir de la espera para chequear el socket
                    break;
                }
            }

            let current_seq = slot.frame_seq.load(Ordering::SeqCst);
            if current_seq != last_seq {
                if let Some(ref frame_arc) = *guard {
                    let frame_bytes = frame_arc.as_slice();
                    let part_hdr = format!(
                        "--txframe\r\nContent-Type: image/jpeg\r\nContent-Length: {}\r\n\r\n",
                        frame_bytes.len()
                    );

                    // Escribir cabecera de la trama y bytes del JPEG
                    if stream.write_all(part_hdr.as_bytes()).is_err() {
                        break;
                    }
                    if stream.write_all(frame_bytes).is_err() {
                        break;
                    }
                    if stream.write_all(b"\r\n").is_err() {
                        break;
                    }

                    last_seq = current_seq;
                }
            } else {
                // Si la cámara no emite aún, verificar si el cliente sigue conectado con un ping de boundary
                let ping = b"--txframe\r\nContent-Type: text/plain\r\nContent-Length: 0\r\n\r\n\r\n";
                if stream.write_all(ping).is_err() {
                    break;
                }
            }
        }
        return;
    }

    // Ruta por defecto 404
    let not_found = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n";
    let _ = stream.write_all(not_found.as_bytes());
}
