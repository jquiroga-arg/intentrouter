#!/usr/bin/env bash
# Instalación orientada a Linux (Ubuntu) + GPU NVIDIA (CUDA) para este proyecto.
# Ejecutar desde la raíz del repo: chmod +x install-linux-cuda.sh && ./install-linux-cuda.sh
#
# Compatibilidad CUDA: los wheels cu124 funcionan con drivers CUDA 12.x y 13.x
# (retrocompatibilidad NVIDIA). Si tu stack usa cu118 o cu126+, ajustá la URL
# según https://pytorch.org/get-started/locally/

set -euo pipefail
cd "$(dirname "$0")"

echo "Creando venv .venv …"
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi

PIP=".venv/bin/pip"
PYTHON=".venv/bin/python"

echo "Actualizando pip …"
"$PYTHON" -m pip install --upgrade pip

# Instalar torch primero con --index-url (exclusivo) para garantizar el wheel
# CUDA. Con --extra-index-url pip puede elegir el wheel CPU de PyPI en su lugar.
echo ""
echo "Instalando PyTorch CUDA 12.4 (compatible con drivers 12.x y 13.x) …"
"$PIP" install "torch>=2.3.0,<2.8.0" --index-url https://download.pytorch.org/whl/cu124

# torch ya está instalado; requirements.txt instalará el resto desde PyPI.
echo ""
echo "Instalando dependencias del proyecto …"
"$PIP" install -r requirements.txt

echo ""
echo "Comprobación rápida de CUDA en PyTorch:"
"$PYTHON" -c "import torch; print('torch           :', torch.__version__); print('cuda_available  :', torch.cuda.is_available()); print('device          :', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A (CPU mode)')"

echo ""
echo "Listo. Activá el entorno con:"
echo "  source .venv/bin/activate"
echo "Config Linux (opcional en esta sesión):"
echo "  export RUTEADOR_CONFIG=\"\$(pwd)/config.linux-cuda.json\""
echo "Luego: python -m ruteador_semantico"
