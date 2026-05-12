"""Chat en consola: semantic-router (rutas desde CSV) + respuestas vía Ollama."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

import ollama
import requests
from semantic_router.encoders import HuggingFaceEncoder
from semantic_router.routers import SemanticRouter

from ruteador_semantico.load_config import default_config_path, load_app_config, resolve_path
from ruteador_semantico.ollama_llm import INTENT_JSON_SCHEMA, ConfigurableOllamaLLM
from ruteador_semantico.routes_csv import routes_from_intents_csv

logger = logging.getLogger("ruteador")


def _configure_logging() -> None:
    """Configura logging desde la variable de entorno RUTEADOR_LOG_LEVEL (default: INFO)."""
    level_name = os.environ.get("RUTEADOR_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def _print_routes_banner(cfg: Mapping[str, Any], routes: list) -> None:
    print()
    print("=" * 60)
    print(
        f"Rutas Semantic Router — entorno={cfg.get('environment')} "
        f"branch={cfg.get('branch')}"
    )
    print("=" * 60)
    for r in routes:
        utts = getattr(r, "utterances", []) or []
        print(f"\n· Ruta: {r.name}")
        print(f"  Ejemplos ({len(utts)}):")
        for i, u in enumerate(utts, 1):
            preview = u if len(u) <= 120 else u[:117] + "..."
            print(f"    {i:2}. {preview}")
    print()
    print("=" * 60)
    print()


def _resolve_cuda_device(requested: str) -> str:
    """Si se pide CUDA pero no está disponible, retorna 'cpu' como fallback seguro.

    Evita el crash de HuggingFaceEncoder cuando torch no tiene soporte CUDA
    (wheel CPU instalado, drivers ausentes, etc.).
    """
    if "cuda" not in requested.lower():
        return requested
    try:
        import torch
    except ImportError:
        logger.warning(
            'device="%s" solicitado pero torch no está instalado → usando "cpu". '
            "Verificá la instalación de PyTorch (ver requirements.txt).",
            requested,
        )
        return "cpu"
    if torch.cuda.is_available():
        try:
            logger.info("PyTorch CUDA: %s", torch.cuda.get_device_name(0))
        except Exception:
            logger.info("PyTorch CUDA: GPU detectada.")
        return requested
    logger.warning(
        'device="%s" solicitado pero torch.cuda.is_available() es False → usando "cpu". '
        "Verificá que el wheel de PyTorch tenga soporte CUDA "
        "(wheel CPU instalado por defecto si se usa --extra-index-url). "
        "Reinstalá con: pip install torch>=2.3.0 "
        "--index-url https://download.pytorch.org/whl/cu124",
        requested,
    )
    return "cpu"


def _build_encoder(enc_cfg: Mapping[str, Any]) -> HuggingFaceEncoder:
    device = str(enc_cfg.get("device") or "").strip()
    if "cuda" in device.lower():
        device = _resolve_cuda_device(device)
    kwargs: dict[str, Any] = {
        "name": enc_cfg.get("name", "sentence-transformers/all-MiniLM-L6-v2"),
        "score_threshold": enc_cfg.get("score_threshold", 0.5),
    }
    if device:
        kwargs["device"] = device
    return HuggingFaceEncoder(**kwargs)


def _maybe_pull_model(host: str, model: str, do_pull: bool) -> None:
    if not do_pull:
        return
    client = ollama.Client(host=host)
    logger.info("Comprobando/descargando modelo Ollama: %r …", model)
    client.pull(model)


def _post_with_retry(
    url: str, payload: dict, timeout: float, max_retries: int
) -> requests.Response:
    """HTTP POST con reintentos exponenciales. No reintenta errores de cliente (4xx)."""
    last_exc: Exception = RuntimeError("Sin intentos")
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise
            last_exc = exc
        except Exception as exc:
            last_exc = exc
        if attempt < max_retries:
            wait = 2 ** attempt
            logger.debug(
                "Ollama no disponible (intento %d/%d), reintentando en %ds: %s",
                attempt + 1, max_retries + 1, wait, last_exc,
            )
            time.sleep(wait)
    raise last_exc


def _load_classifier_prompt(cfg: dict, base_dir: Path) -> str | None:
    """Carga el prompt del clasificador LLM desde el archivo configurado."""
    sr_cfg = cfg.get("semantic_router", {}) or {}
    prompt_file = sr_cfg.get("classifier_prompt_file")
    if not prompt_file:
        return None
    path = resolve_path(base_dir, str(prompt_file))
    if not path.is_file():
        logger.warning("classifier_prompt_file no encontrado: %s", path)
        return None
    return path.read_text(encoding="utf-8-sig")


def _llm_classify(
    user_text: str,
    classifier_prompt: str,
    host: str,
    model: str,
    timeout: float,
    max_retries: int,
) -> str:
    """Clasificador LLM de fallback. Retorna el nombre de intención en mayúsculas."""
    resp = _post_with_retry(
        f"{host}/api/chat",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": classifier_prompt},
                {"role": "user", "content": user_text},
            ],
            "think": False,
            "stream": False,
            "format": INTENT_JSON_SCHEMA,
            "options": {"temperature": 0.0, "num_predict": 128},
        },
        timeout,
        max_retries,
    )
    try:
        data = json.loads(resp.json()["message"]["content"])
        intent = str(data.get("intent", "inexistente")).upper()
        confidence = float(data.get("confidence", 0.0))
        logger.debug("LLM clasificó → %s (confianza=%.2f)", intent, confidence)
        return intent
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("LLM clasificador retornó JSON inválido; usando INEXISTENTE")
        return "INEXISTENTE"


def run(config_path: Path | None = None) -> None:
    raw_cfg, base_dir, resolved_config = load_app_config(config_path)
    cfg: dict[str, Any] = dict(raw_cfg)
    logger.info("Configuración: %s", resolved_config)

    intents_rel = cfg.get("intents_csv", "Test/intents.csv")
    intents_path = resolve_path(base_dir, str(intents_rel))
    if not intents_path.is_file():
        raise FileNotFoundError(f"No se encontró el CSV de intenciones: {intents_path}")

    ollama_cfg = cfg.get("ollama", {}) or {}
    host = str(ollama_cfg.get("host", "http://127.0.0.1:11434")).rstrip("/")
    os.environ["OLLAMA_HOST"] = host
    max_retries = int(ollama_cfg.get("max_retries", 3))

    model_cfg = cfg.get("router_model", {}) or {}
    model_name = str(model_cfg.get("name", "qwen3.5:9b"))
    chat_timeout = float(ollama_cfg.get("chat_timeout_seconds", 120))

    _maybe_pull_model(
        host,
        model_name,
        bool(ollama_cfg.get("pull_on_startup", True)),
    )

    routes = routes_from_intents_csv(intents_path)
    if not routes:
        raise RuntimeError("No se generó ninguna ruta: revisa el CSV.")

    sr_cfg = cfg.get("semantic_router", {}) or {}
    enc_cfg = sr_cfg.get("encoder", {}) or {}
    encoder = _build_encoder(enc_cfg)

    llm = ConfigurableOllamaLLM(
        name=model_name,
        ollama_host=host,
        temperature=float(model_cfg.get("temperature", 0.1)),
        max_tokens=int(model_cfg.get("max_tokens", 512)),
        stream=False,
        request_timeout=chat_timeout,
        max_retries=max_retries,
    )

    router = SemanticRouter(
        encoder=encoder,
        routes=routes,
        llm=llm,
        top_k=int(sr_cfg.get("top_k", 5)),
        aggregation=str(sr_cfg.get("aggregation", "mean")),
        auto_sync=sr_cfg.get("auto_sync", "local"),
    )

    _print_routes_banner(cfg, routes)

    chat_cfg = cfg.get("chat", {}) or {}
    system_template = str(
        chat_cfg.get(
            "system_prompt",
            "Intención: {route_name}. Responde en español, breve.",
        )
    )
    exit_cmds = {
        x.strip().lower()
        for x in (chat_cfg.get("exit_commands") or ["salir", "exit", "quit"])
    }

    llm_fallback = bool(sr_cfg.get("llm_fallback", False))
    classifier_prompt = _load_classifier_prompt(cfg, base_dir) if llm_fallback else None
    if llm_fallback and classifier_prompt is None:
        logger.warning(
            "llm_fallback=true pero no se pudo cargar el prompt clasificador; "
            "el fallback quedará desactivado."
        )
        llm_fallback = False

    logger.info(
        "Iniciando chat — modelo=%s | fallback-LLM=%s",
        model_name,
        "sí" if llm_fallback else "no",
    )
    print("\nChat municipal (semantic-router + Ollama). Escribe 'salir' para terminar.\n")

    while True:
        try:
            user = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós.")
            break
        if not user:
            continue
        if user.lower() in exit_cmds:
            print("Adiós.")
            break

        choice = router(user)
        route_name = getattr(choice, "name", None)

        if route_name is None and llm_fallback:
            logger.debug("Embedding router sin coincidencia; activando clasificador LLM")
            label = _llm_classify(
                user, classifier_prompt, host, model_name, chat_timeout, max_retries
            )
        else:
            label = route_name if route_name else "null"

        logger.info("intención detectada: %s", label)

        system_content = system_template.format(route_name=label)
        try:
            resp = _post_with_retry(
                f"{host}/api/chat",
                {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user},
                    ],
                    "think": False,
                    "stream": False,
                    "options": {
                        "temperature": float(model_cfg.get("temperature", 0.1)),
                        "num_predict": int(model_cfg.get("max_tokens", 512)),
                    },
                },
                chat_timeout,
                max_retries,
            )
            text = resp.json()["message"]["content"].strip()
            print(f"Asistente: {text}\n")
        except Exception as e:
            logger.error("Error al llamar a Ollama: %s", e)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Chat consola con semantic-router + Ollama")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Ruta a config.json (por defecto: RUTEADOR_CONFIG o ./config.json junto al proyecto)",
    )
    args = parser.parse_args()
    path = args.config.resolve() if args.config else default_config_path()
    run(path)


if __name__ == "__main__":
    main()
