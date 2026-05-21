"""Tests para _resolve_cuda_device: fallback CPU cuando CUDA no está disponible."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _cuda_reinstall_hint
# ---------------------------------------------------------------------------

def test_cuda_reinstall_hint_windows():
    from ruteador_semantico.main import _cuda_reinstall_hint

    with patch.object(sys, "platform", "win32"):
        assert _cuda_reinstall_hint() == "./install-windows-cuda.ps1"


def test_cuda_reinstall_hint_linux():
    from ruteador_semantico.main import _cuda_reinstall_hint

    with patch.object(sys, "platform", "linux"):
        assert _cuda_reinstall_hint() == "./install-linux-cuda.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_resolve(monkeypatch, torch_mock):
    """Parchea sys.modules['torch'] y retorna la función bajo test."""
    monkeypatch.setitem(sys.modules, "torch", torch_mock)
    # Reimportar para que la función use el mock en sys.modules al ejecutarse
    from ruteador_semantico.main import _resolve_cuda_device
    return _resolve_cuda_device


# ---------------------------------------------------------------------------
# Dispositivos no-CUDA: deben pasar sin llamar a torch
# ---------------------------------------------------------------------------

def test_cpu_device_passthrough():
    """'cpu' no debe invocar torch y debe retornarse sin cambios."""
    from ruteador_semantico.main import _resolve_cuda_device
    assert _resolve_cuda_device("cpu") == "cpu"


def test_mps_device_passthrough():
    """'mps' (Apple Silicon) no debe invocar torch y debe retornarse sin cambios."""
    from ruteador_semantico.main import _resolve_cuda_device
    assert _resolve_cuda_device("mps") == "mps"


# ---------------------------------------------------------------------------
# CUDA solicitado, torch NO instalado (ImportError)
# ---------------------------------------------------------------------------

def test_resolve_cuda_falls_back_to_cpu_on_import_error(monkeypatch):
    """Sin torch instalado (ImportError) debe retornar 'cpu'."""
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    from ruteador_semantico.main import _resolve_cuda_device
    assert _resolve_cuda_device("cuda") == "cpu"
    assert _resolve_cuda_device("cuda:0") == "cpu"


# ---------------------------------------------------------------------------
# CUDA solicitado, torch instalado pero CUDA NO disponible
# (escenario del usuario: wheel CPU instalado por error)
# ---------------------------------------------------------------------------

def test_resolve_cuda_falls_back_when_cuda_unavailable(monkeypatch):
    """torch.cuda.is_available()=False debe retornar 'cpu' y no crashear."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    fn = _get_resolve(monkeypatch, mock_torch)
    assert fn("cuda") == "cpu"
    assert fn("cuda:1") == "cpu"


# ---------------------------------------------------------------------------
# CUDA solicitado, torch instalado y CUDA disponible (caso feliz)
# ---------------------------------------------------------------------------

def test_resolve_cuda_returns_requested_when_available(monkeypatch):
    """torch.cuda.is_available()=True debe retornar el device solicitado."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4090"

    fn = _get_resolve(monkeypatch, mock_torch)
    assert fn("cuda") == "cuda"
    assert fn("cuda:0") == "cuda:0"


def test_resolve_cuda_handles_get_device_name_error(monkeypatch):
    """Si get_device_name() falla, no debe crashear y el device sigue siendo CUDA."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.side_effect = RuntimeError("no device")

    fn = _get_resolve(monkeypatch, mock_torch)
    assert fn("cuda") == "cuda"


# ---------------------------------------------------------------------------
# Integración: _build_encoder usa cpu cuando CUDA no disponible
# ---------------------------------------------------------------------------

def test_build_encoder_receives_cpu_when_cuda_unavailable(monkeypatch):
    """_build_encoder debe pasar 'cpu' a HuggingFaceEncoder si CUDA no está disponible."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    captured: dict = {}

    def fake_hf_encoder(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("ruteador_semantico.main.HuggingFaceEncoder", fake_hf_encoder)

    from ruteador_semantico.main import _build_encoder
    _build_encoder({
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "device": "cuda",
        "score_threshold": 0.5,
    })

    assert captured.get("device") == "cpu", (
        f"Se esperaba 'cpu' pero HuggingFaceEncoder recibió device={captured.get('device')!r}"
    )
