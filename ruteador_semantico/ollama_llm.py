"""Ollama LLM compatible con semantic-router usando host configurable.

La implementación incluida en semantic_router.llms.ollama usa una URL fija
localhost; aquí se respeta la clave ollama.host del config.json.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

import requests
from pydantic import ConfigDict, Field

from semantic_router.llms.base import BaseLLM
from semantic_router.schema import Message
from semantic_router.utils.logger import logger

# Schema JSON del clasificador: {"intent":..., "confidence":..., "secondary_intent":...}
INTENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "secondary_intent": {
            "anyOf": [{"type": "string"}, {"type": "null"}]
        },
    },
    "required": ["intent", "confidence", "secondary_intent"],
    "additionalProperties": False,
}


class ConfigurableOllamaLLM(BaseLLM):
    """Misma API HTTP que OllamaLLM upstream, con base URL configurable."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ollama_host: str = Field(default="http://127.0.0.1:11434")
    stream: bool = Field(default=False)
    request_timeout: float = Field(default=120.0)
    max_retries: int = Field(default=3)
    response_format: Any = Field(default=None)

    def __init__(
        self,
        name: str,
        *,
        ollama_host: str = "http://127.0.0.1:11434",
        temperature: float = 0.2,
        max_tokens: Optional[int] = 200,
        stream: bool = False,
        request_timeout: float = 120.0,
        max_retries: int = 3,
        response_format: Any = None,
    ):
        host = ollama_host.rstrip("/")
        super().__init__(
            name=name,
            temperature=temperature,
            max_tokens=max_tokens,
            ollama_host=host,
            stream=stream,
            request_timeout=request_timeout,
            max_retries=max_retries,
            response_format=response_format,
        )

    def __call__(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        stream: Optional[bool] = None,
    ) -> Optional[str]:
        temperature = temperature if temperature is not None else self.temperature
        model_name = name if name is not None else self.name
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        stream = stream if stream is not None else self.stream
        fmt = self.response_format if self.response_format is not None else INTENT_JSON_SCHEMA

        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": model_name,
            "messages": [m.to_openai() for m in messages],
            "think": False,
            "format": fmt,
            "stream": stream,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        last_exc: Exception = RuntimeError("Sin intentos")
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.request_timeout)
                response.raise_for_status()
                return response.json()["message"]["content"]
            except requests.exceptions.HTTPError as exc:
                # No reintentar errores de cliente (4xx)
                if exc.response is not None and 400 <= exc.response.status_code < 500:
                    logger.error("LLM HTTP error del cliente: %s", exc)
                    raise Exception(f"LLM error: {exc}") from exc
                last_exc = exc
            except Exception as exc:
                last_exc = exc
            if attempt < self.max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "LLM request fallido (intento %d/%d), reintentando en %ds",
                    attempt + 1, self.max_retries + 1, wait,
                )
                time.sleep(wait)

        logger.error("LLM error tras %d reintentos: %s", self.max_retries, last_exc)
        raise Exception(f"LLM error: {last_exc}") from last_exc
