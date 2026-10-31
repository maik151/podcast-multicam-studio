use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::Instant;

/// Representa el búfer circular "Latest-Frame-Only" de una cámara.
pub struct CameraSlot {
    pub id: usize,
    pub target_port: Mutex<u16>,
    pub platform: Mutex<String>,
    pub is_connected: AtomicBool,
    pub frame_seq: AtomicU64,
    pub fps_x10: AtomicU32, // FPS multiplicado por 10 (ej. 598 = 59.8 fps)
    pub latest_frame: Mutex<Option<Arc<Vec<u8>>>>,
    pub condvar: Condvar,
    pub frame_count: AtomicU64,
    pub last_fps_calc: Mutex<Instant>,
}

impl CameraSlot {
    pub fn new(id: usize, default_port: u16) -> Self {
        Self {
            id,
            target_port: Mutex::new(default_port),
            platform: Mutex::new("android".to_string()),
            is_connected: AtomicBool::new(false),
            frame_seq: AtomicU64::new(0),
            fps_x10: AtomicU32::new(0),
            latest_frame: Mutex::new(None),
            condvar: Condvar::new(),
            frame_count: AtomicU64::new(0),
            last_fps_calc: Mutex::new(Instant::now()),
        }
    }

    /// Publica un nuevo fotograma JPEG completo en el slot.
    /// Si un cliente está leyendo lento, el fotograma anterior se sobreescribe inmediatamente (Zero-Latency).
    pub fn push_frame(&self, frame: Vec<u8>) {
        let frame_arc = Arc::new(frame);
        {
            let mut guard = self.latest_frame.lock().unwrap();
            *guard = Some(frame_arc);
        }
        self.frame_seq.fetch_add(1, Ordering::SeqCst);
        self.is_connected.store(true, Ordering::SeqCst);

        // Cálculo de FPS dinámico cada segundo
        let count = self.frame_count.fetch_add(1, Ordering::Relaxed) + 1;
        let mut last_calc = self.last_fps_calc.lock().unwrap();
        let elapsed = last_calc.elapsed().as_secs_f64();
        if elapsed >= 1.0 {
            let fps = (count as f64) / elapsed;
            self.fps_x10.store((fps * 10.0) as u32, Ordering::Relaxed);
            self.frame_count.store(0, Ordering::Relaxed);
            *last_calc = Instant::now();
        }

        // Notificar a todos los clientes HTTP que hay un fotograma listo
        self.condvar.notify_all();
    }

    /// Marca el slot como desconectado y limpia el fotograma
    pub fn set_disconnected(&self) {
        self.is_connected.store(false, Ordering::SeqCst);
        self.fps_x10.store(0, Ordering::Relaxed);
        let mut guard = self.latest_frame.lock().unwrap();
        *guard = None;
    }

    pub fn get_port(&self) -> u16 {
        *self.target_port.lock().unwrap()
    }

    pub fn set_port(&self, port: u16) {
        let mut p = self.target_port.lock().unwrap();
        *p = port;
    }

    pub fn get_platform(&self) -> String {
        self.platform.lock().unwrap().clone()
    }

    pub fn set_platform(&self, plat: &str) {
        let mut p = self.platform.lock().unwrap();
        *p = plat.to_string();
    }
}
