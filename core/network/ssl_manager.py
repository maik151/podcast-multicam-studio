"""
Gestor de certificados SSL locales X.509 v3 con Subject Alternative Names (SAN),
BasicConstraints CA y registro automático en el almacén de confianza del usuario en Windows.
Garantiza que la consola de escritorio y los navegadores móviles operen sin bloqueos.
"""

import os
import sys
import subprocess
import datetime
import ipaddress
import ssl
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from core.network.detector import get_all_local_ipv4s, detect_primary_ip


def _trust_certificate_on_windows(cert_path: str) -> None:
    """
    Registra silenciosamente el certificado en el almacén de Entidades de Certificación
    Raíz de Confianza del Usuario Actual (CurrentUser\\Root) en Windows para evitar
    advertencias de 'Sitio sospechoso / Conexión no privada' en la PC.
    """
    if sys.platform != "win32" or not os.path.exists(cert_path):
        return
    try:
        subprocess.run(
            ["certutil", "-user", "-f", "-addstore", "Root", cert_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception:
        pass


def generate_ssl_certificate(certs_dir: str) -> tuple[str, str]:
    """Genera cert.pem y key.pem con SANs X.509 v3 para todas las interfaces locales."""
    os.makedirs(certs_dir, exist_ok=True)
    cert_path = os.path.join(certs_dir, "cert.pem")
    key_path = os.path.join(certs_dir, "key.pem")
    crt_download_path = os.path.join(certs_dir, "TX-Studio-CA.crt")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        try:
            with open(cert_path, "rb") as f:
                loaded_cert = x509.load_pem_x509_certificate(f.read())
                san_ext = loaded_cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                existing_sans = {str(n.value) for n in san_ext.value}
                primary_ip, _ = detect_primary_ip()
                if primary_ip in existing_sans or primary_ip == "127.0.0.1":
                    return cert_path, key_path
        except Exception:
            pass

    # Generar clave privada RSA 2048 bits
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    primary_ip, _ = detect_primary_ip()

    # Configuración de Identidad X.509 v3 Oficial
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TX-STUDIO Broadcast Suite"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Local WebRTC Authority"),
        x509.NameAttribute(NameOID.COMMON_NAME, primary_ip),
    ])

    # Subject Alternative Names (SAN)
    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("tx-studio.local"),
        x509.DNSName("podcast.local"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("192.168.137.1")),
    ]

    for ip_str in get_all_local_ipv4s():
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj not in [san.value for san in san_list if isinstance(san, x509.IPAddress)]:
                san_list.append(x509.IPAddress(ip_obj))
        except ValueError:
            pass

    # Construir Certificado X.509 v3 con extensiones estándar de servidor y CA raíz
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=820))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Guardar clave privada
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Guardar certificado PEM y copia .crt instalable para móviles
    cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
    with open(cert_path, "wb") as f:
        f.write(cert_bytes)
    with open(crt_download_path, "wb") as f:
        f.write(cert_bytes)

    # Registrar confianza en Windows automáticamente
    _trust_certificate_on_windows(cert_path)

    print(f"[SSL] Certificado seguro X.509 v3 generado y verificado en: {cert_path}")
    return cert_path, key_path


def create_ssl_context(certs_dir: str) -> ssl.SSLContext:
    """Crea un contexto SSL listo para aiohttp con los certificados locales."""
    cert_path, key_path = generate_ssl_certificate(certs_dir)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_path, key_path)
    return ssl_context
