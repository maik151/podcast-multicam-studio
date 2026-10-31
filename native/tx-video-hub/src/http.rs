use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::logger;
use crate::slot::CameraSlot;

pub const HTTP_PORT: u16 = 9100;

/// Inicia el servidor HTTP multihilo de streaming en el puerto 9100.
pub fn start_http_server(slots: Arc<Vec<Arc<CameraSlot>>>) {
    let listener = TcpListener::bind(format!("0.0.0.0:{}", HTTP_PORT))
        .expect("Fallo al enlazar puerto 9100 para tx-video-hub");

    logger::info("SERVER", &format!("Servidor de video nativo activo en http://0.0.0.0:{}", HTTP_PORT));

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
    let _ = stream.set_read_timeout(Some(Duration::from_millis(4000)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(5000)));

    let mut buf = [0u8; 4096];
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
            "Access-Control-Allow-Headers: Content-Type, Content-Length\r\n",
            "Content-Length: 0\r\n",
            "\r\n"
        );
        let _ = stream.write_all(resp.as_bytes());
        return;
    }

    // Ruta de Bind Dinámico: POST /bind
    if method == "POST" && path == "/bind" {
        let content_len = extract_header_val(&req_str, "Content-Length:")
            .and_then(|v| v.parse::<usize>().ok())
            .unwrap_or(0);

        if let Some(body_start) = req_str.find("\r\n\r\n") {
            let start = body_start + 4;
            let mut body_bytes = Vec::new();
            if n > start {
                body_bytes.extend_from_slice(&buf[start..n]);
            }

            while body_bytes.len() < content_len {
                let mut chunk = [0u8; 1024];
                let remaining = content_len - body_bytes.len();
                let to_read = remaining.min(chunk.len());
                match stream.read(&mut chunk[..to_read]) {
                    Ok(0) => break,
                    Ok(rn) => body_bytes.extend_from_slice(&chunk[..rn]),
                    Err(_) => break,
                }
            }

            let body = String::from_utf8_lossy(&body_bytes);
            let cam_id = extract_json_u32(&body, "cam_id").unwrap_or(1) as usize;
            let platform = extract_json_str(&body, "platform").unwrap_or("android");
            let port = extract_json_u32(&body, "port").unwrap_or(4741) as u16;
            let dev_id = extract_json_u32(&body, "device_id");

            if let Some(slot) = slots.iter().find(|s| s.id == cam_id) {
                slot.set_platform(platform);
                slot.set_port(port);
                slot.set_device_id(dev_id);
                logger::info(
                    "BIND",
                    &format!("CAM 0{} vinculada: platform={}, port={}, dev_id={:?}", cam_id, platform, port, dev_id)
                );
                let resp = concat!(
                    "HTTP/1.1 200 OK\r\n",
                    "Content-Type: application/json\r\n",
                    "Access-Control-Allow-Origin: *\r\n",
                    "Content-Length: 17\r\n",
                    "\r\n",
                    "{\"success\": true}"
                );
                let _ = stream.write_all(resp.as_bytes());
                return;
            }
        }
    }

    // Ruta de Ingesta Wi-Fi / Hotspot: POST /push/1, /push/2, /push/3
    if method == "POST" && path.starts_with("/push/") {
        let id_str = path.trim_start_matches("/push/").split('?').next().unwrap_or("1");
        let cam_id: usize = id_str.parse().unwrap_or(1);

        if let Some(slot) = slots.iter().find(|s| s.id == cam_id) {
            let content_len = extract_header_val(&req_str, "Content-Length:")
                .and_then(|v| v.parse::<usize>().ok())
                .unwrap_or(0);

            if content_len > 0 && content_len < 10 * 1024 * 1024 {
                let body_start = match req_str.find("\r\n\r\n") {
                    Some(idx) => idx + 4,
                    None => return,
                };

                let mut frame_data = Vec::with_capacity(content_len);
                if n > body_start {
                    frame_data.extend_from_slice(&buf[body_start..n]);
                }

                while frame_data.len() < content_len {
                    let mut chunk = [0u8; 65536];
                    let remaining = content_len - frame_data.len();
                    let to_read = remaining.min(chunk.len());
                    match stream.read(&mut chunk[..to_read]) {
                        Ok(0) => break,
                        Ok(rn) => frame_data.extend_from_slice(&chunk[..rn]),
                        Err(_) => break,
                    }
                }

                if frame_data.len() == content_len {
                    slot.push_frame(frame_data);
                    let resp = "HTTP/1.1 204 No Content\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: 0\r\n\r\n";
                    let _ = stream.write_all(resp.as_bytes());
                    return;
                }
            }
        }
    }

    if path == "/status" {
        let mut cam_json = String::new();
        for (i, slot) in slots.iter().enumerate() {
            let fps = (slot.fps_x10.load(Ordering::Relaxed) as f64) / 10.0;
            let conn = slot.is_connected.load(Ordering::Relaxed);
            let port = slot.get_port();
            let plat = slot.get_platform();
            let dev_id = slot.get_device_id().unwrap_or(0);
            if i > 0 {
                cam_json.push_str(", ");
            }
            cam_json.push_str(&format!(
                "\"{}\": {{\"connected\": {}, \"fps\": {:.1}, \"port\": {}, \"platform\": \"{}\", \"device_id\": {}}}",
                slot.id, conn, fps, port, plat, dev_id
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

        let header = concat!(
            "HTTP/1.1 200 OK\r\n",
            "Content-Type: multipart/x-mixed-replace; boundary=txframe\r\n",
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

            while slot.frame_seq.load(Ordering::SeqCst) == last_seq {
                let res = slot.condvar.wait_timeout(guard, Duration::from_millis(200)).unwrap();
                guard = res.0;
                if res.1.timed_out() {
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
            }
        }
        return;
    }

    let not_found = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n";
    let _ = stream.write_all(not_found.as_bytes());
}

fn extract_json_u32(json: &str, key: &str) -> Option<u32> {
    let key_pat = format!("\"{}\"", key);
    let pos = json.find(&key_pat)? + key_pat.len();
    let colon_pos = json[pos..].find(':')? + 1;
    let after = json[pos + colon_pos..].trim();
    let num_str: String = after.chars().take_while(|c| c.is_ascii_digit()).collect();
    if num_str.is_empty() {
        None
    } else {
        num_str.parse().ok()
    }
}

fn extract_json_str<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    let key_pat = format!("\"{}\"", key);
    let pos = json.find(&key_pat)? + key_pat.len();
    let colon_pos = json[pos..].find(':')? + 1;
    let after = json[pos + colon_pos..].trim();
    if after.starts_with('"') {
        let after_quote = &after[1..];
        let end = after_quote.find('"')?;
        Some(&after_quote[..end])
    } else {
        None
    }
}

fn extract_header_val<'a>(headers: &'a str, key: &str) -> Option<&'a str> {
    for line in headers.lines() {
        if line.to_ascii_lowercase().starts_with(&key.to_ascii_lowercase()) {
            return Some(line[key.len()..].trim());
        }
    }
    None
}
