"""
Gestor de puertos y sanitización de sockets para evitar Errno 10048 en Windows.
"""

import os
import sys
import subprocess
import socket
import time

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Verifica si un puerto TCP específico está actualmente en escucha."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

def release_port_if_busy(port: int = 8443, auto_kill: bool = True) -> bool:
    """
    Detecta si el puerto está ocupado por una instancia previa de Python
    y la finaliza para evitar 'Errno 10048: solo se permite un uso de cada dirección de socket'.
    """
    if not is_port_in_use(port):
        return True

    print(f"[PORT] Puerto {port} detectado en uso. Analizando procesos previos...")

    current_pid = os.getpid()

    if sys.platform == "win32":
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # Consultar con netstat los PIDs en escucha en el puerto
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL, creationflags=no_win)
            
            pids_to_kill = set()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    pid_str = parts[-1]
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid != current_pid and pid != 0:
                            pids_to_kill.add(pid)

            if not pids_to_kill:
                print(f"[PORT] El puerto {port} está ocupado pero no se detectaron PIDs huérfanos específicos.")
                return False

            if auto_kill:
                for pid in pids_to_kill:
                    print(f"[PORT] [AUTO-CLEAN] Cerrando proceso previo (PID: {pid}) en puerto {port}...")
                    try:
                        subprocess.run(
                            f"taskkill /F /PID {pid}",
                            shell=True,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=no_win
                        )
                    except Exception as e:
                        print(f"[PORT] No se pudo finalizar PID {pid}: {e}")

                # Dar 500ms al sistema operativo para liberar el socket
                time.sleep(0.5)
                
                if not is_port_in_use(port):
                    print(f"[PORT] [OK] Puerto {port} liberado exitosamente.")
                    return True
                else:
                    print(f"[PORT] [AVISO] Puerto {port} aun ocupado tras intento de liberacion.")
                    return False

        except Exception as e:
            print(f"[PORT] Error durante la inspección de puertos: {e}")

    return False
