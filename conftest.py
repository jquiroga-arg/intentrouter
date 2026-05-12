"""Configuración de pytest: agrega el directorio raíz al path para que los imports funcionen."""

from __future__ import annotations

import sys
from pathlib import Path

# Permite importar ruteador_semantico sin necesidad de instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent))
