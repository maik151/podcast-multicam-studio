"""
================================================================================
SUITE DE VALIDACIÓN AUTOMÁTICA DE ACEPTACIÓN: SPRINT 0
(Infraestructura, Red, Arquitectura Modular y Pipeline de Arranque)
================================================================================
"""

import sys
import os
import io
import json
import time
import shutil
import qrcode
import qrcode.image.svg

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = r"C:\Proyects\GITHUB_REPOS\Proyects_repo\podcast_multicam_studio"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import PORT, HOST, CERTS_DIR, RECORDINGS_DIR, STATIC_DIR
from core.network.detector import get_network_diagnostics, detect_primary_ip, get_all_local_ipv4s
from core.network.port_manager import release_port_if_busy, is_port_in_use
from core.network.ssl_manager import generate_ssl_certificate, create_ssl_context
from core.telemetry.system_telemetry import get_system_telemetry
from core.recording.recorder_service import RecorderService
from core.recording.markers_service import MarkersService
from core.signaling.webrtc_router import WebRtcRouter
from core.signaling.hub import SignalingHub
import main

test_results = []

def record(name: str, passed: bool, info: str = ""):
    tag = "[PASS]" if passed else "[FAIL]"
    test_results.append((tag, name, info))
    print(f" {tag} | {name:<35} | {info}")

def run_tests():
    print("\n" + "=" * 75)
    print(" 🚀 INICIANDO VALIDACIÓN TÉCNICA RIGUROSA - SPRINT 0")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # TEST 1: DETECCIÓN DE RED Y ADAPTADORES 100% OFFLINE (Tarea 0.1)
    # -------------------------------------------------------------------------
    print("\n[FASE 1] Detección de Red y Adaptadores Offline")
    try:
        ip, net_type = detect_primary_ip()
        all_ips = get_all_local_ipv4s()
        diag = get_network_diagnostics(PORT)

        is_valid_ip = bool(ip and ip != "0.0.0.0" and not ip.startswith("255."))
        record("Detección de IP Primaria", is_valid_ip, f"IP: {ip} ({net_type})")
        record("Inspección de Interfaces Locales", len(all_ips) > 0, f"Total detectadas: {len(all_ips)} -> {all_ips}")
        record("Generación de Base URL HTTPS", diag.get("base_url") == f"https://{ip}:{PORT}", diag.get("base_url"))
    except Exception as e:
        record("Detección de Red", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 2: SANITIZACIÓN Y LIBERACIÓN DE PUERTOS (Tarea 0.3)
    # -------------------------------------------------------------------------
    print("\n[FASE 2] Sanitización de Socket y Prevención de Errno 10048")
    try:
        in_use_initial = is_port_in_use(PORT)
        freed = release_port_if_busy(PORT, auto_kill=True)
        record("Evaluación de Socket en 8443", freed is True, f"En uso previo: {in_use_initial} | Liberado: {freed}")
    except Exception as e:
        record("Sanitización de Socket", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 3: INFRAESTRUCTURA SSL Y CERTIFICADOS CON SAN MULTI-IP
    # -------------------------------------------------------------------------
    print("\n[FASE 3] Infraestructura SSL y Certificados SAN")
    try:
        cert_path, key_path = generate_ssl_certificate(CERTS_DIR)
        has_cert = os.path.exists(cert_path) and os.path.getsize(cert_path) > 200
        has_key = os.path.exists(key_path) and os.path.getsize(key_path) > 200
        record("Certificado X.509 cert.pem", has_cert, f"{cert_path} ({os.path.getsize(cert_path)} bytes)")
        record("Clave Privada RSA key.pem", has_key, f"{key_path} ({os.path.getsize(key_path)} bytes)")

        ssl_ctx = create_ssl_context(CERTS_DIR)
        record("Contexto TLS aiohttp", ssl_ctx is not None, "Contexto seguro instanciado correctamente con cert_chain")
    except Exception as e:
        record("Infraestructura SSL", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 4: TELEMETRÍA DEL HOST WINDOWS (ctypes Windows API)
    # -------------------------------------------------------------------------
    print("\n[FASE 4] Telemetría del Sistema Host (ctypes Windows API)")
    try:
        metrics = get_system_telemetry(RECORDINGS_DIR)
        has_fields = all(k in metrics for k in ["cpu_percent", "ram_used_gb", "ram_total_gb", "disk_free_gb", "disk_warning"])
        record("Métricas de Telemetría Completas", has_fields, f"RAM: {metrics.get('ram_used_gb')}/{metrics.get('ram_total_gb')} GB | Disco: {metrics.get('disk_free_gb')} GB Libres")
    except Exception as e:
        record("Telemetría de Hardware", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 5: DE-OFUSCADOR mDNS Y ENRUTADOR WEBRTC
    # -------------------------------------------------------------------------
    print("\n[FASE 5] De-ofuscación de mDNS y Enrutamiento WebRTC")
    try:
        sample_cand = {
            "type": "candidate",
            "camId": 1,
            "candidate": {
                "candidate": "candidate:842163049 1 udp 1686052607 4f6b2170-b747-49f3.local 54321 typ host",
                "sdpMid": "0"
            }
        }
        res_json = WebRtcRouter.deobfuscate_mdns(sample_cand, "192.168.100.70")
        has_real_ip = "192.168.100.70" in res_json and ".local" not in res_json
        record("Reemplazo mDNS .local -> IP LAN", has_real_ip, "Candidato ICE des-ofuscado a IPv4 real correctamente")
    except Exception as e:
        record("De-ofuscador mDNS", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 6: MOTOR DE GRABACIÓN REAL A DISCO (RecorderService)
    # -------------------------------------------------------------------------
    print("\n[FASE 6] Motor de Grabación a Disco y Streaming de Chunks")
    try:
        test_rec_dir = os.path.join(RECORDINGS_DIR, "Test_Sprint0")
        recorder = RecorderService(test_rec_dir)

        # Iniciar toma de prueba
        start_res = recorder.start_take(project="Test_Sprint0", episode="Ep_Test", take=1, resolution="1080p", fps=60, ext="webm")
        record("Inicio de Toma en Disco", start_res.get("status") == "recording_started", f"Archivo: {start_res.get('file')}")

        # Escribir 3 chunks simulados de 100 KB
        dummy_chunk = b"\x00\x01\x02\x03" * 25000 # 100 KB
        chunk_res = recorder.write_chunk(dummy_chunk)
        record("Escritura de Chunk Binario", chunk_res.get("status") == "chunk_written", f"Escritos: {chunk_res.get('bytes')} B | Total: {chunk_res.get('total_mb')} MB")

        # Sellar toma
        stop_res = recorder.stop_take()
        file_exists = os.path.exists(stop_res.get("path")) and stop_res.get("bytes") == len(dummy_chunk)
        record("Sellado de Toma en Disco", file_exists, f"Sellado: {stop_res.get('size_mb')} MB | Path: {stop_res.get('path')}")

        # Limpiar carpeta de test
        shutil.rmtree(test_rec_dir, ignore_errors=True)
    except Exception as e:
        record("Motor de Grabación", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 7: SERVICIO DE MARCADORES (MarkersService)
    # -------------------------------------------------------------------------
    print("\n[FASE 7] Servicio de Marcadores de Clips (REC FLAG)")
    try:
        test_markers_dir = os.path.join(RECORDINGS_DIR, "Test_Markers")
        markers = MarkersService(test_markers_dir)

        m_res = markers.add_marker(project="Test_Proj", episode="Ep_01", take=1, timecode_str="00:05:23:12", note="Prueba de clip", count=1)
        record("Creación de Marcador Timecode", m_res.get("status") == "marker_added", f"Marcador creado: {m_res.get('marker')}")

        txt_file = os.path.join(test_markers_dir, "Test_Proj", "Ep_01", "Toma_01_Marcadores.txt")
        json_file = os.path.join(test_markers_dir, "Test_Proj", "Ep_01", "Toma_01_Marcadores.json")
        has_reports = os.path.exists(txt_file) and os.path.exists(json_file)
        record("Generación Dual TXT & JSON", has_reports, "Archivos de reporte para edición creados")

        shutil.rmtree(test_markers_dir, ignore_errors=True)
    except Exception as e:
        record("Servicio de Marcadores", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 8: GENERADOR VECTORIAL QR SVG (Sin PIL)
    # -------------------------------------------------------------------------
    print("\n[FASE 8] Generador Nativo de Códigos QR en SVG")
    try:
        target_url = "https://192.168.100.70:8443/cam/1"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
            image_factory=qrcode.image.svg.SvgPathImage
        )
        qr.add_data(target_url)
        qr.make(fit=True)
        img = qr.make_image()
        buf = io.BytesIO()
        img.save(buf)
        svg_bytes = buf.getvalue()

        is_valid_svg = b"<svg" in svg_bytes and b"</svg>" in svg_bytes and len(svg_bytes) > 500
        record("Generador QR Vectorial SVG", is_valid_svg, f"SVG válido generado ({len(svg_bytes)} bytes)")
    except Exception as e:
        record("Generador QR SVG", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # TEST 9: INTEGRIDAD DE CLIENTES ESTÁTICOS (Director & Mobile PWA)
    # -------------------------------------------------------------------------
    print("\n[FASE 9] Integridad de Archivos de Clientes Web")
    try:
        dir_html = os.path.join(STATIC_DIR, "director", "index.html")
        dir_js = os.path.join(STATIC_DIR, "director", "app.js")
        mob_html = os.path.join(STATIC_DIR, "mobile", "index.html")
        mob_js = os.path.join(STATIC_DIR, "mobile", "app.js")
        mob_jsqr = os.path.join(STATIC_DIR, "mobile", "jsqr.min.js")

        all_exist = all(os.path.exists(p) and os.path.getsize(p) > 1000 for p in [dir_html, dir_js, mob_html, mob_js, mob_jsqr])
        record("Archivos de Consola del Director", os.path.exists(dir_html) and os.path.exists(dir_js), f"HTML: {os.path.getsize(dir_html)} B | JS: {os.path.getsize(dir_js)} B")
        record("Archivos PWA Móvil y jsQR", os.path.exists(mob_html) and os.path.exists(mob_js) and os.path.exists(mob_jsqr), f"HTML: {os.path.getsize(mob_html)} B | JS: {os.path.getsize(mob_js)} B | jsQR: {os.path.getsize(mob_jsqr)} B")
    except Exception as e:
        record("Integridad de Archivos Estáticos", False, f"Excepción: {e}")

    # -------------------------------------------------------------------------
    # BALANCE FINAL
    # -------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" 📊 RESUMEN FINAL DE PRUEBAS DE VALIDACIÓN - SPRINT 0")
    print("=" * 75)

    total = len(test_results)
    passed = sum(1 for tag, _, _ in test_results if tag == "[PASS]")
    failed = total - passed

    for tag, name, info in test_results:
        print(f" {tag} | {name:<35} | {info}")

    print("-" * 75)
    print(f" Total Pruebas: {total} | Aprobadas: {passed} | Fallidas: {failed}")

    if failed == 0:
        print("\n ✅ SPRINT 0: 100% DE PRUEBAS APROBADAS Y VALIDACIÓN COMPLETA.\n")
        return 0
    else:
        print(f"\n ❌ SPRINT 0: EXISTEN {failed} PRUEBAS FALLIDAS.\n")
        return 1

if __name__ == "__main__":
    code = run_tests()
    sys.exit(code)
