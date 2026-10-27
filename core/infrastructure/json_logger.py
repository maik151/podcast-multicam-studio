"""
Sistema de Trazabilidad Total y Matriz de Logs Estructurados en JSON para TX-STUDIO.
Permite ejecución 100% silenciosa sin consola CMD (GUI Subsystem) registrando
todos los eventos de Backend, Frontend (Consola Director), Cámaras Móviles (PWA),
WebRTC, Grabador, Audio DSP, Red y Errores con trazabilidad exacta (archivo, línea, función y stacktrace).

Archivos generados en `Documentos/TX-STUDIO/Logs/`:
1. `tx_studio_events.jsonl` — Historial completo de eventos en tiempo real (JSON Lines).
2. `latest_session.json`    — Resumen matricial de la sesión actual + últimos eventos.
3. `error_matrix.json`      — Matriz diagnóstica de advertencias/errores (Dónde ocurrió, Por qué ocurrió, Frecuencia).
"""

import os
import sys
import json
import uuid
import datetime
import traceback
import threading


class JsonSystemLogger:
    def __init__(self, logs_dir: str):
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        self.jsonl_path = os.path.join(self.logs_dir, "tx_studio_events.jsonl")
        self.session_json_path = os.path.join(self.logs_dir, "latest_session.json")
        self.error_matrix_path = os.path.join(self.logs_dir, "error_matrix.json")

        self.session_id = datetime.datetime.now().strftime("SES-%Y%m%d-%H%M%S-") + str(uuid.uuid4())[:6].upper()
        self.started_at = datetime.datetime.now().isoformat(timespec="milliseconds")
        self._lock = threading.Lock()
        self._seq = 0
        self._session_events = []
        self._counts_by_level = {"INFO": 0, "WARN": 0, "ERROR": 0, "CRITICAL": 0}
        self._counts_by_category = {}
        self._counts_by_component = {}
        self._error_catalog = self._load_existing_error_matrix()

    def _load_existing_error_matrix(self) -> dict:
        if os.path.isfile(self.error_matrix_path):
            try:
                with open(self.error_matrix_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "incidents" in data:
                        return data["incidents"]
            except Exception:
                pass
        return {}

    def log(
        self,
        level: str,
        component: str,
        message: str,
        details: dict = None,
        category: str = None,
        source: str = "BACKEND",
        action: str = None
    ) -> dict:
        lvl = (level or "INFO").upper()
        if lvl == "WARNING":
            lvl = "WARN"
        comp = (component or "SYSTEM").upper()
        cat = (category or self._infer_category(comp, message)).upper()
        act = (action or self._infer_action(comp, message)).upper()
        now_iso = datetime.datetime.now().isoformat(timespec="milliseconds")

        with self._lock:
            self._seq += 1
            entry = {
                "event_id": f"{self.session_id}-{self._seq:05d}",
                "session_id": self.session_id,
                "timestamp": now_iso,
                "level": lvl,
                "source": (source or "BACKEND").upper(),
                "category": cat,
                "component": comp,
                "action": act,
                "message": (message or "").strip(),
                "details": details or {}
            }

            self._counts_by_level[lvl] = self._counts_by_level.get(lvl, 0) + 1
            self._counts_by_category[cat] = self._counts_by_category.get(cat, 0) + 1
            self._counts_by_component[comp] = self._counts_by_component.get(comp, 0) + 1

            try:
                with open(self.jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                self._session_events.append(entry)
                if len(self._session_events) > 500:
                    self._session_events = self._session_events[-500:]

                # Si es WARN, ERROR o CRITICAL, actualizar la matriz de diagnóstico de fallos
                if lvl in ("WARN", "ERROR", "CRITICAL"):
                    self._record_in_error_matrix(entry)

                self._persist_session_snapshot(now_iso)
            except Exception:
                pass

            return entry

    def log_exception(
        self,
        component: str,
        action: str,
        exc: BaseException,
        context_details: dict = None,
        source: str = "BACKEND"
    ) -> dict:
        """Extrae archivo exacto, línea, función, tipo de excepción y stacktrace completo."""
        tb_list = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
        origin_file = "unknown"
        origin_line = 0
        origin_func = "unknown"
        if tb_list:
            last_frame = tb_list[-1]
            origin_file = os.path.basename(last_frame.filename)
            origin_line = last_frame.lineno
            origin_func = last_frame.name

        details = dict(context_details or {})
        details.update({
            "exception_type": type(exc).__name__,
            "exception_reason": str(exc),
            "where_file": origin_file,
            "where_line": origin_line,
            "where_function": origin_func,
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        })
        return self.log(
            level="ERROR",
            component=component,
            message=f"{type(exc).__name__} en {origin_file}:{origin_line} ({origin_func}): {exc}",
            details=details,
            category="EXCEPTION_TRACE",
            source=source,
            action=action
        )

    def _record_in_error_matrix(self, entry: dict) -> None:
        key = f"{entry['source']}::{entry['component']}::{entry['action']}"
        details = entry.get("details") or {}
        existing = self._error_catalog.get(key)
        if existing:
            existing["occurrences"] = existing.get("occurrences", 1) + 1
            existing["last_seen"] = entry["timestamp"]
            existing["last_message"] = entry["message"]
            existing["last_details"] = details
        else:
            self._error_catalog[key] = {
                "signature": key,
                "level": entry["level"],
                "source": entry["source"],
                "category": entry["category"],
                "component": entry["component"],
                "action": entry["action"],
                "first_seen": entry["timestamp"],
                "last_seen": entry["timestamp"],
                "occurrences": 1,
                "where_occurred": {
                    "file": details.get("where_file", details.get("url", entry["component"])),
                    "line": details.get("where_line", 0),
                    "function": details.get("where_function", entry["action"])
                },
                "why_occurred": details.get("exception_reason", entry["message"]),
                "last_message": entry["message"],
                "last_details": details
            }

        try:
            with open(self.error_matrix_path, "w", encoding="utf-8") as ef:
                json.dump({
                    "application": "TX-STUDIO Professional Broadcast Suite",
                    "version": "1.0.0",
                    "updated_at": entry["timestamp"],
                    "total_unique_incidents": len(self._error_catalog),
                    "incidents": self._error_catalog
                }, ef, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _persist_session_snapshot(self, updated_at: str) -> None:
        recent_errors = [
            e for e in self._session_events[-100:]
            if e.get("level") in ("WARN", "ERROR", "CRITICAL")
        ][-25:]

        with open(self.session_json_path, "w", encoding="utf-8") as sf:
            json.dump({
                "application": "TX-STUDIO Professional Broadcast Suite",
                "version": "1.0.0",
                "session_id": self.session_id,
                "started_at": self.started_at,
                "updated_at": updated_at,
                "telemetry_matrix": {
                    "total_events": self._seq,
                    "by_level": self._counts_by_level,
                    "by_category": self._counts_by_category,
                    "by_component": self._counts_by_component,
                },
                "recent_warnings_and_errors": recent_errors,
                "events": self._session_events
            }, sf, indent=2, ensure_ascii=False)

    def get_matrix_summary(self) -> dict:
        with self._lock:
            return {
                "session_id": self.session_id,
                "started_at": self.started_at,
                "logs_dir": self.logs_dir,
                "files": {
                    "events_jsonl": self.jsonl_path,
                    "latest_session": self.session_json_path,
                    "error_matrix": self.error_matrix_path
                },
                "telemetry_matrix": {
                    "total_events": self._seq,
                    "by_level": dict(self._counts_by_level),
                    "by_category": dict(self._counts_by_category),
                    "by_component": dict(self._counts_by_component),
                },
                "error_incidents_count": len(self._error_catalog),
                "recent_events": self._session_events[-30:]
            }

    @staticmethod
    def _infer_category(comp: str, msg: str) -> str:
        c = comp.upper()
        m = msg.upper()
        if "WS" in c or "SIGNAL" in c or "WEBRTC" in c or "SDP" in m or "ICE" in m:
            return "WEBRTC_SIGNALING"
        if "REC" in c or "MARCADOR" in c or "TOMA" in m:
            return "RECORDER"
        if "SSL" in c or "PORT" in c or "RED" in c or "NET" in c or "FIREWALL" in c:
            return "NETWORK"
        if "AUDIO" in c or "DSP" in c:
            return "AUDIO_DSP"
        if "SWITCH" in c or "PGM" in c or "TBAR" in c:
            return "SWITCHER"
        if "HTTP" in c or "API" in c:
            return "HTTP_API"
        return "SYSTEM"

    @staticmethod
    def _infer_action(comp: str, msg: str) -> str:
        m = msg.lower()
        if "conectado" in m or "connect" in m:
            return "CONNECTED"
        if "desconectado" in m or "disconnect" in m:
            return "DISCONNECTED"
        if "iniciando" in m or "start" in m:
            return "START"
        if "sellada" in m or "stop" in m or "detenid" in m:
            return "STOP"
        if "certificado" in m or "ssl" in m:
            return "SSL_VERIFY"
        if "error" in m or "fallo" in m or "exception" in m:
            return "ERROR_EVENT"
        return f"{comp.upper()}_EVENT"


class _StreamToJsonAdapter:
    """Adaptador de flujo para capturar print() y errores cuando no hay consola CMD activa."""
    def __init__(self, logger: JsonSystemLogger, default_level: str = "INFO", orig_stream=None):
        self.logger = logger
        self.default_level = default_level
        self.orig_stream = orig_stream
        self.encoding = "utf-8"

    def write(self, buf: str) -> int:
        if self.orig_stream is not None:
            try:
                self.orig_stream.write(buf)
            except Exception:
                pass
        if not buf or not buf.strip():
            return len(buf) if buf else 0

        for line in buf.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("==="):
                continue
            comp = "SYSTEM"
            lvl = self.default_level
            if clean.startswith("[") and "]" in clean:
                comp = clean[1:clean.index("]")].strip()
                clean = clean[clean.index("]") + 1:].strip()
            if "⚠️" in clean or "warn" in clean.lower():
                lvl = "WARN"
            elif "❌" in clean or "error" in clean.lower() or "traceback" in clean.lower():
                lvl = "ERROR"
            self.logger.log(lvl, comp, clean)
        return len(buf)

    def flush(self) -> None:
        if self.orig_stream is not None:
            try:
                self.orig_stream.flush()
            except Exception:
                pass

    def reconfigure(self, **kwargs) -> None:
        pass


_global_logger: JsonSystemLogger | None = None


def init_json_logger(logs_dir: str) -> JsonSystemLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = JsonSystemLogger(logs_dir)
    return _global_logger


def get_json_logger() -> JsonSystemLogger | None:
    return _global_logger


def log_event(
    component: str,
    message: str,
    details: dict = None,
    level: str = "INFO",
    category: str = None,
    source: str = "BACKEND",
    action: str = None
) -> None:
    if _global_logger is not None:
        _global_logger.log(
            level=level,
            component=component,
            message=message,
            details=details,
            category=category,
            source=source,
            action=action
        )


def log_exception(
    component: str,
    action: str,
    exc: BaseException,
    context_details: dict = None,
    source: str = "BACKEND"
) -> None:
    if _global_logger is not None:
        _global_logger.log_exception(
            component=component,
            action=action,
            exc=exc,
            context_details=context_details,
            source=source
        )
