mod http;
mod ingest;
mod slot;
mod usbmuxd;

use std::sync::Arc;
use std::thread;
use std::time::Duration;

use slot::CameraSlot;

fn main() {
    println!("============================================================");
    println!("   TX-VIDEO-HUB // MOTOR NATIVO DE TRANSMISIÓN DE VIDEO     ");
    println!("   Cero Latencia | Zero-Copy MJPEG 60 FPS | Android & iOS   ");
    println!("============================================================");

    // Inicializar los 3 slots de cámara para las entradas del estudio
    let slot1 = Arc::new(CameraSlot::new(1, 4741));
    let slot2 = Arc::new(CameraSlot::new(2, 4742));
    let slot3 = Arc::new(CameraSlot::new(3, 4743));

    let slots = Arc::new(vec![
        Arc::clone(&slot1),
        Arc::clone(&slot2),
        Arc::clone(&slot3),
    ]);

    // Iniciar los 3 hilos de captura e ingesta en segundo plano
    ingest::start_ingest_worker(Arc::clone(&slot1));
    ingest::start_ingest_worker(Arc::clone(&slot2));
    ingest::start_ingest_worker(Arc::clone(&slot3));

    // Iniciar el servidor HTTP multihilo de ultra-alto rendimiento en puerto 9100
    http::start_http_server(Arc::clone(&slots));

    println!("[tx-video-hub] Listo para recibir conexiones en http://127.0.0.1:9100");

    // Mantener vivo el proceso principal
    loop {
        thread::sleep(Duration::from_secs(60));
    }
}
