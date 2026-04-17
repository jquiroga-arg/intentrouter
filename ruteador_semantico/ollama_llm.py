"""Ollama LLM compatible con semantic-router usando host configurable.

La implementación incluida en semantic_router.llms.ollama usa una URL fija
localhost; aquí se respeta la clave ollama.host del config.json.
"""

from __future__ import annotations

from typing import List, Optional

import requests
from pydantic import ConfigDict, Field

from semantic_router.llms.base import BaseLLM
from semantic_router.schema import Message
from semantic_router.utils.logger import logger


class ConfigurableOllamaLLM(BaseLLM):
    """Misma API HTTP que OllamaLLM upstream, con base URL configurable."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ollama_host: str = Field(default="http://127.0.0.1:11434")
    stream: bool = Field(default=False)
    request_timeout: float = Field(default=120.0)

    def __init__(
        self,
        name: str,
        *,
        ollama_host: str = "http://127.0.0.1:11434",
        temperature: float = 0.2,
        max_tokens: Optional[int] = 200,
        stream: bool = False,
        request_timeout: float = 120.0,
    ):
        host = ollama_host.rstrip("/")
        super().__init__(
            name=name,
            temperature=temperature,
            max_tokens=max_tokens,
            ollama_host=host,
            stream=stream,
            request_timeout=request_timeout,
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

        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": model_name,
            "messages": [m.to_openai() for m in messages],
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "format": "json",
            "stream": stream,
        }
        try:
            response = requests.post(
                url, json=payload, timeout=self.request_timeout
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            logger.error("LLM error: %s", e)
            raise Exception(f"LLM error: {e}") from e
