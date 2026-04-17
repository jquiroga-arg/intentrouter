"""Chat en consola: semantic-router (rutas desde CSV) + respuestas vía Ollama."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import ollama
from semantic_router.encoders import HuggingFaceEncoder
from semantic_router.routers import SemanticRouter

from ruteador_semantico.load_config import default_config_path, load_app_config, resolve_path
from ruteador_semantico.ollama_llm import ConfigurableOllamaLLM
from ruteador_semantico.routes_csv import routes_from_intents_csv


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


def _build_encoder(enc_cfg: Mapping[str, Any]) -> HuggingFaceEncoder:
    kwargs: dict[str, Any] = {
        "name": enc_cfg.get("name", "sentence-transformers/all-MiniLM-L6-v2"),
        "score_threshold": enc_cfg.get("score_threshold", 0.5),
    }
    device = enc_cfg.get("device")
    if device is not None and str(device).strip() != "":
        kwargs["device"] = str(device).strip()
    return HuggingFaceEncoder(**kwargs)


def _log_cuda_encoder_status(enc_cfg: Mapping[str, Any]) -> None:
    """Avisa si el config pide CUDA y PyTorch no ve GPU (drivers / wheel incorrecto)."""
    device = enc_cfg.get("device")
    if device is None or str(device).strip() == "":
        return
    if "cuda" not in str(device).lower():
        return
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        try:
            print(f"PyTorch CUDA: {torch.cuda.get_device_name(0)}")
        except Exception:
            print("PyTorch CUDA: GPU detectada.")
        return
    print(
        "\n[ADVERTENCIA] semantic_router.encoder.device usa CUDA pero "
        "torch.cuda.is_available() es False.\n"
        "  Revisa: drivers NVIDIA, instalación de torch con CUDA (requirements.txt) "
        "y que la GPU no esté ocupada exclusivamente por otro proceso.\n"
        "  Mientras tanto puedes poner \"device\": \"cpu\" en config.json.\n",
        file=sys.stderr,
    )


def _maybe_pull_model(host: str, model: str, do_pull: bool) -> None:
    if not do_pull:
        return
    client = ollama.Client(host=host)
    print(f"Comprobando/descargando modelo Ollama: {model!r} …")
    client.pull(model)


def run(config_path: Path | None = None) -> None:
    raw_cfg, base_dir, resolved_config = load_app_config(config_path)
    cfg: dict[str, Any] = dict(raw_cfg)
    print(f"Configuración: {resolved_config}")

    intents_rel = cfg.get("intents_csv", "Test/intents.csv")
    intents_path = resolve_path(base_dir, str(intents_rel))
    if not intents_path.is_file():
        raise FileNotFoundError(f"No se encontró el CSV de intenciones: {intents_path}")

    ollama_cfg = cfg.get("ollama", {}) or {}
    host = str(ollama_cfg.get("host", "http://127.0.0.1:11434")).rstrip("/")
    os.environ["OLLAMA_HOST"] = host

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
    _log_cuda_encoder_status(enc_cfg)
    encoder = _build_encoder(enc_cfg)

    llm = ConfigurableOllamaLLM(
        name=model_name,
        ollama_host=host,
        temperature=float(model_cfg.get("temperature", 0.3)),
        max_tokens=int(model_cfg.get("max_tokens", 512)),
        stream=False,
        request_timeout=chat_timeout,
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

    ollama_client = ollama.Client(host=host)

    print("Chat municipal (semantic-router + Ollama). Escribe 'salir' para terminar.\n")
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
        label = route_name if route_name else "null"
        print(f"[router] intención: {label}")

        system_content = system_template.format(route_name=label)
        try:
            resp = ollama_client.chat(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user},
                ],
                options={
                    "temperature": float(model_cfg.get("temperature", 0.3)),
                    "num_predict": int(model_cfg.get("max_tokens", 512)),
                },
            )
            text = (resp.get("message") or {}).get("content", "").strip()
            print(f"Asistente: {text}\n")
        except Exception as e:
            print(f"Error llamando a Ollama: {e}\n", file=sys.stderr)


def main() -> None:
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
