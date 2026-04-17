# Instalación orientada a Windows + GPU NVIDIA (CUDA) para este proyecto.
# Ejecutar desde la raíz del repo en PowerShell (puede requerir ExecutionPolicy remota una vez).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Creando venv .venv …"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$pip = Join-Path ".venv" "Scripts\pip.exe"
$python = Join-Path ".venv" "Scripts\python.exe"

Write-Host "Actualizando pip …"
& $python -m pip install --upgrade pip

Write-Host "Instalando dependencias (PyTorch CUDA 12.4 + semantic-router) …"
& $pip install -r requirements.txt

Write-Host "`nComprobación rápida de CUDA en PyTorch:"
& $python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available());
print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

Write-Host "`nListo. Activa el entorno con:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Luego: python -m ruteador_semantico"
