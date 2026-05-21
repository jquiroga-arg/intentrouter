"""Tests para load_config.py — carga de configuración JSON."""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path

from ruteador_semantico.load_config import (
    default_config_path,
    load_app_config,
    resolve_path,
)


# ---------------------------------------------------------------------------
# load_app_config
# ---------------------------------------------------------------------------

def test_load_valid_config(tmp_path):
    cfg = {"branch": "test", "environment": "linux-cpu", "intents_csv": "Test/intents.csv"}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    data, base_dir, resolved = load_app_config(p)

    assert data["branch"] == "test"
    assert data["environment"] == "linux-cpu"
    assert base_dir == tmp_path
    assert resolved == p.resolve()


def test_missing_config_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="config.json"):
        load_app_config(tmp_path / "nonexistent.json")


def test_returns_correct_base_dir(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    p = subdir / "config.json"
    p.write_text('{"x": 1}', encoding="utf-8")

    _, base_dir, _ = load_app_config(p)

    assert base_dir == subdir


def test_utf8_bom_handling(tmp_path):
    """config.json guardado con BOM (Excel/Notepad en Windows) debe parsearse correctamente."""
    cfg = {"branch": "bom-test", "environment": "windows-cuda"}
    p = tmp_path / "config.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(cfg).encode("utf-8"))

    data, _, _ = load_app_config(p)

    assert data["branch"] == "bom-test"


def test_nested_config_preserved(tmp_path):
    cfg = {
        "ollama": {"host": "http://localhost:11434", "max_retries": 3},
        "router_model": {"name": "qwen3.5:9b", "temperature": 0.1},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")

    data, _, _ = load_app_config(p)

    assert data["ollama"]["max_retries"] == 3
    assert data["router_model"]["temperature"] == 0.1


def test_empty_json_object(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{}", encoding="utf-8")
    data, _, _ = load_app_config(p)
    assert data == {}


# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------

def test_resolve_absolute_path_unchanged(tmp_path):
    abs_path = tmp_path / "some" / "file.csv"
    result = resolve_path(tmp_path, str(abs_path))
    assert result == abs_path


def test_resolve_relative_path(tmp_path):
    result = resolve_path(tmp_path, "Test/intents.csv")
    assert result == (tmp_path / "Test" / "intents.csv").resolve()


def test_resolve_simple_filename(tmp_path):
    result = resolve_path(tmp_path, "intents.csv")
    assert result == (tmp_path / "intents.csv").resolve()


def test_resolve_dot_relative(tmp_path):
    result = resolve_path(tmp_path, "./data/file.csv")
    assert result == (tmp_path / "data" / "file.csv").resolve()


# ---------------------------------------------------------------------------
# default_config_path
# ---------------------------------------------------------------------------

def test_default_config_path_uses_env_var(tmp_path, monkeypatch):
    fake_cfg = tmp_path / "my_config.json"
    monkeypatch.setenv("RUTEADOR_CONFIG", str(fake_cfg))
    result = default_config_path()
    assert result == fake_cfg.resolve()


def test_default_config_path_fallback_to_package_dir(monkeypatch):
    monkeypatch.delenv("RUTEADOR_CONFIG", raising=False)
    result = default_config_path()
    # Debe terminar en config.json
    assert result.name == "config.json"
    # Debe estar en el directorio padre del paquete
    assert result.parent.name == "intentrouter" or (result.parent / "ruteador_semantico").is_dir()


def test_load_linux_cuda_config_from_repo_root():
    """config.linux-cuda.json del repo debe cargarse y resolver rutas relativas."""
    repo_root = Path(__file__).resolve().parent.parent
    cfg_path = repo_root / "config.linux-cuda.json"
    if not cfg_path.is_file():
        pytest.skip("config.linux-cuda.json no presente en el repo")

    data, base_dir, resolved = load_app_config(cfg_path)

    assert data["environment"] == "linux-cuda"
    assert base_dir == repo_root
    intents = resolve_path(base_dir, str(data["intents_csv"]))
    assert intents == (repo_root / "Test" / "intents.csv").resolve()
    assert intents.is_file()
