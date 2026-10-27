"""
Wrapper de compatibilidad retroactiva para Podcast Multicam Studio.
Redirige la ejecución a la nueva arquitectura modular en main.py.
"""

import sys
import os

# Asegurar que el directorio raíz esté en sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from main import main

if __name__ == "__main__":
    main()
