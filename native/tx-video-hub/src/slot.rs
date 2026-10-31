use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::Instant;

/// Representa el búfer circular "Latest-Frame-Only" de una cámara.
pub struct CameraSlot {
    pub id: usize,
    pub target_port: Mutex<u16>,
    pub platform: Mutex<String>,
    pub device_id: Mutex<Option<u32>>,
    pub is_connected: AtomicBool,
    pub frame_seq: AtomicU64,
    pub fps_x10: AtomicU32,
    pub latest_frame: Mutex<Option<Arc<Vec<u8>>>>,
    pub condvar: Condvar,
    pub frame_count: AtomicU64,
    pub last_fps_calc: Mutex<Instant>,
    pub force_reconnect: AtomicBool,
}

impl CameraSlot {
    pub fn new(id: usize, default_port: u16) -> Self {
        Self {
            id,
            target_port: Mutex::new(default_port),
            platform: Mutex::new("android".to_string()),
            device_id: Mutex::new(None),
            is_connected: AtomicBool::new(false),
            frame_seq: AtomicU64::new(0),
            fps_x10: AtomicU32::new(0),
            latest_frame: Mutex::new(None),
            condvar: Condvar::new(),
            frame_count: AtomicU64::new(0),
            last_fps_calc: Mutex::new(Instant::now()),
            force_reconnect: AtomicBool::new(false),
        }
    }

    /// Publica un nuevo fotograma JPEG completo en el slot.
    pub fn push_frame(&self, frame: Vec<u8>) {
        let frame_arc = Arc::new(frame);
        {
            let mut guard = self.latest_frame.lock().unwrap();
            *guard = Some(frame_arc);
        }
        self.frame_seq.fetch_add(1, Ordering::SeqCst);
        self.is_connected.store(true, Ordering::SeqCst);

        let count = self.frame_count.fetch_add(1, Ordering::Relaxed) + 1;
        let mut last_calc = self.last_fps_calc.lock().unwrap();
        let elapsed = last_calc.elapsed().as_secs_f64();
        if elapsed >= 1.0 {
            let fps = (count as f64) / elapsed;
            self.fps_x10.store((fps * 10.0) as u32, Ordering::Relaxed);
            self.frame_count.store(0, Ordering::Relaxed);
            *last_calc = Instant::now();
        }

        self.condvar.notify_all();
    }

    pub fn set_disconnected(&self) {
        if self.is_connected.swap(false, Ordering::SeqCst) {
            crate::logger::info(
                &format!("CAM-{}", self.id),
                "Cámara desconectada o esperando flujo"
            );
        }
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
        self.force_reconnect.store(true, Ordering::SeqCst);
    }

    pub fn get_platform(&self) -> String {
        self.platform.lock().unwrap().clone()
    }

    pub fn set_platform(&self, plat: &str) {
        let mut p = self.platform.lock().unwrap();
        *p = plat.to_string();
        self.force_reconnect.store(true, Ordering::SeqCst);
    }

    pub fn get_device_id(&self) -> Option<u32> {
        *self.device_id.lock().unwrap()
    }

    pub fn set_device_id(&self, dev_id: Option<u32>) {
        let mut d = self.device_id.lock().unwrap();
        *d = dev_id;
        self.force_reconnect.store(true, Ordering::SeqCst);
    }
}
