use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::SystemTime;

static LOGGER: Mutex<Option<Logger>> = Mutex::new(None);

pub struct Logger {
    file_path: PathBuf,
}

impl Logger {
    pub fn init() {
        // Buscar la carpeta Logs/ en el directorio de ejecución o subiendo niveles
        let mut log_dir = PathBuf::from("Logs");
        if !log_dir.exists() {
            let alt = PathBuf::from("../Logs");
            if alt.exists() {
                log_dir = alt;
            } else {
                let alt2 = PathBuf::from("../../Logs");
                if alt2.exists() {
                    log_dir = alt2;
                } else {
                    let _ = create_dir_all(&log_dir);
                }
            }
        }

        let file_path = log_dir.join("video_hub.log");
        let mut guard = LOGGER.lock().unwrap();
        *guard = Some(Logger { file_path });
    }

    pub fn log(level: &str, target: &str, msg: &str) {
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Formato timestamp legible aproximado o UNIX
        let log_line = format!("[{}] [{}] [{}] {}\n", now, level, target, msg);
        print!("{}", log_line);

        if let Ok(guard) = LOGGER.lock() {
            if let Some(logger) = guard.as_ref() {
                if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&logger.file_path) {
                    let _ = f.write_all(log_line.as_bytes());
                }
            }
        }
    }
}

pub fn info(target: &str, msg: &str) {
    Logger::log("INFO", target, msg);
}

pub fn warn(target: &str, msg: &str) {
    Logger::log("WARN", target, msg);
}

pub fn error(target: &str, msg: &str) {
    Logger::log("ERROR", target, msg);
}
