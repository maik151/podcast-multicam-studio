use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

pub const USBMUXD_PORT: u16 = 27015;

/// Intenta conectar a una app en un iPhone a través de usbmuxd.
/// Retorna el TcpStream conectado al socket del iPhone o None si falló.
pub fn connect_iphone_port(device_id: u32, target_port: u16) -> Option<TcpStream> {
    let mut stream = TcpStream::connect_timeout(
        &format!("127.0.0.1:{}", USBMUXD_PORT).parse().ok()?,
        Duration::from_millis(800),
    ).ok()?;

    stream.set_read_timeout(Some(Duration::from_millis(1500))).ok()?;
    stream.set_write_timeout(Some(Duration::from_millis(1500))).ok()?;

    // usbmuxd requiere el puerto con bytes invertidos (network byte order / htons)
    let swapped_port: u32 = (((target_port << 8) & 0xFF00) | (target_port >> 8)) as u32;

    let payload = format!(
        concat!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n",
            "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n",
            "<plist version=\"1.0\">\n",
            "<dict>\n",
            "  <key>MessageType</key><string>Connect</string>\n",
            "  <key>ClientVersionString</key><string>tx-video-hub</string>\n",
            "  <key>ProgName</key><string>tx-video-hub</string>\n",
            "  <key>DeviceID</key><integer>{}</integer>\n",
            "  <key>PortNumber</key><integer>{}</integer>\n",
            "</dict>\n",
            "</plist>"
        ),
        device_id, swapped_port
    );

    let payload_bytes = payload.as_bytes();
    let length = (16 + payload_bytes.len()) as u32;
    let version: u32 = 1;
    let request_type: u32 = 8; // MESSAGE_PLIST
    let tag: u32 = 1;

    let mut header = Vec::with_capacity(16);
    header.extend_from_slice(&length.to_le_bytes());
    header.extend_from_slice(&version.to_le_bytes());
    header.extend_from_slice(&request_type.to_le_bytes());
    header.extend_from_slice(&tag.to_le_bytes());

    stream.write_all(&header).ok()?;
    stream.write_all(payload_bytes).ok()?;
    stream.flush().ok()?;

    // Leer encabezado de respuesta (16 bytes)
    let mut resp_hdr = [0u8; 16];
    stream.read_exact(&mut resp_hdr).ok()?;

    let resp_len = u32::from_le_bytes([resp_hdr[0], resp_hdr[1], resp_hdr[2], resp_hdr[3]]) as usize;
    if resp_len < 16 {
        return None;
    }

    let mut body = vec![0u8; resp_len - 16];
    stream.read_exact(&mut body).ok()?;

    let body_str = String::from_utf8_lossy(&body);
    // Number == 0 indica conexión exitosa a nivel usbmuxd
    if body_str.contains("<key>Number</key><integer>0</integer>")
        || body_str.contains("<key>Number</key>\n\t<integer>0</integer>")
        || body_str.contains("<integer>0</integer>") {
        // La conexión ahora es un túnel transparente con el puerto del iPhone
        Some(stream)
    } else {
        None
    }
}

/// Consulta a usbmuxd el primer device_id de iPhone conectado
pub fn get_first_iphone_id() -> Option<u32> {
    let mut stream = TcpStream::connect_timeout(
        &format!("127.0.0.1:{}", USBMUXD_PORT).parse().ok()?,
        Duration::from_millis(500),
    ).ok()?;

    stream.set_read_timeout(Some(Duration::from_millis(1000))).ok()?;
    stream.set_write_timeout(Some(Duration::from_millis(1000))).ok()?;

    let payload = concat!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n",
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n",
        "<plist version=\"1.0\">\n",
        "<dict>\n",
        "  <key>MessageType</key><string>ListDevices</string>\n",
        "  <key>ClientVersionString</key><string>tx-video-hub</string>\n",
        "  <key>ProgName</key><string>tx-video-hub</string>\n",
        "</dict>\n",
        "</plist>"
    );

    let payload_bytes = payload.as_bytes();
    let length = (16 + payload_bytes.len()) as u32;
    let version: u32 = 1;
    let request_type: u32 = 8;
    let tag: u32 = 1;

    let mut header = Vec::with_capacity(16);
    header.extend_from_slice(&length.to_le_bytes());
    header.extend_from_slice(&version.to_le_bytes());
    header.extend_from_slice(&request_type.to_le_bytes());
    header.extend_from_slice(&tag.to_le_bytes());

    stream.write_all(&header).ok()?;
    stream.write_all(payload_bytes).ok()?;
    stream.flush().ok()?;

    let mut resp_hdr = [0u8; 16];
    stream.read_exact(&mut resp_hdr).ok()?;
    let resp_len = u32::from_le_bytes([resp_hdr[0], resp_hdr[1], resp_hdr[2], resp_hdr[3]]) as usize;
    if resp_len < 16 {
        return None;
    }

    let mut body = vec![0u8; resp_len - 16];
    stream.read_exact(&mut body).ok()?;
    let body_str = String::from_utf8_lossy(&body);

    // Buscar <key>DeviceID</key><integer>123</integer>
    if let Some(pos) = body_str.find("<key>DeviceID</key>") {
        let after = &body_str[pos..];
        if let Some(int_start) = after.find("<integer>") {
            let int_str = &after[int_start + 9..];
            if let Some(int_end) = int_str.find("</integer>") {
                let id_str = &int_str[..int_end].trim();
                return id_str.parse::<u32>().ok();
            }
        }
    }
    None
}
