"""Carga de config.json con rutas relativas al archivo de configuración."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def default_config_path() -> Path:
    env = os.environ.get("RUTEADOR_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    return (Path(__file__).resolve().parent.parent / "config.json").resolve()


def load_app_config(path: Path | None = None) -> tuple[Mapping[str, Any], Path, Path]:
    config_path = (path or default_config_path()).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"No existe config.json: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    return data, base, config_path


def resolve_path(base: Path, maybe_relative: str) -> Path:
    p = Path(maybe_relative)
    if p.is_absolute():
        return p
    return (base / p).resolve()
