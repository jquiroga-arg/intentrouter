# Instalación orientada a Windows + GPU NVIDIA (CUDA) para este proyecto.
# Ejecutar desde la raíz del repo en PowerShell (puede requerir ExecutionPolicy remota una vez).
#
# Compatibilidad CUDA: los wheels cu124 funcionan con drivers CUDA 12.x y 13.x
# (retrocompatibilidad NVIDIA). Si tu stack usa cu118 o cu126+, ajustá la URL
# según https://pytorch.org/get-started/locally/

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Creando venv .venv …"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$pip    = Join-Path ".venv" "Scripts\pip.exe"
$python = Join-Path ".venv" "Scripts\python.exe"

Write-Host "Actualizando pip …"
& $python -m pip install --upgrade pip

# Instalar torch primero con --index-url (exclusivo) para garantizar el wheel
# CUDA. Con --extra-index-url pip puede elegir el wheel CPU de PyPI en su lugar.
Write-Host ""
Write-Host "Instalando PyTorch CUDA 12.4 (compatible con drivers 12.x y 13.x) …"
& $pip install "torch>=2.3.0,<2.8.0" --index-url https://download.pytorch.org/whl/cu124

# torch ya está instalado; requirements.txt instalará el resto desde PyPI.
Write-Host ""
Write-Host "Instalando dependencias del proyecto …"
& $pip install -r requirements.txt

Write-Host ""
Write-Host "Comprobación rápida de CUDA en PyTorch:"
& $python -c "import torch; print('torch           :', torch.__version__); print('cuda_available  :', torch.cuda.is_available()); print('device          :', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A (CPU mode)')"

Write-Host ""
Write-Host "Listo. Activá el entorno con:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Config Windows (opcional en esta sesión):"
Write-Host '  $env:RUTEADOR_CONFIG = (Join-Path $PWD "config.json")'
Write-Host "Luego: python -m ruteador_semantico"
