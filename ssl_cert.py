"""
Generador de certificados SSL locales con Subject Alternative Names (SAN).
Incluye localhost, 127.0.0.1, 192.168.137.1 (Hotspot de Windows) y todas las IPs locales detectadas.
Permite que Safari (iOS) y Chrome (Android) activen getUserMedia sin bloqueos de seguridad.
"""

import os
import datetime
import ipaddress
import socket
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def get_all_local_ips():
    """Detecta todas las IPs locales IPv4 de la máquina."""
    ips = {"127.0.0.1", "192.168.137.1"}
    try:
        # Intentar obtener el hostname e IPs asociadas
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    
    # También conectar un socket UDP falso para ver la IP de salida
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
        
    return list(ips)

def generate_ssl_certificate(cert_dir="certs"):
    """Genera cert.pem y key.pem si no existen o devuelve sus rutas."""
    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "cert.pem")
    key_path = os.path.join(cert_dir, "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    # Generar clave privada RSA 2048 bits
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Configurar el Sujeto
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Podcast Multicam Studio Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, "PodcastStudioLocal"),
    ])

    # Lista de SAN (Subject Alternative Names)
    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("podcast.local"),
    ]

    for ip_str in get_all_local_ips():
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass

    # Construir Certificado X.509
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
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

    # Guardar certificado
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[SSL] Certificado generado con éxito en: {cert_path}")
    print(f"[SSL] IPs registradas en SAN: {get_all_local_ips()}")
    return cert_path, key_path

if __name__ == "__main__":
    generate_ssl_certificate()
