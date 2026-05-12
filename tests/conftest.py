"""Mocks de dependencias pesadas (semantic_router, torch) para tests sin GPU."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _install_semantic_router_mock() -> None:
    """Sustituye semantic_router con una implementación mínima para testing."""

    class FakeRoute:
        """Route mínimo: solo name y utterances."""

        def __init__(self, name: str, utterances: list):
            self.name = name
            self.utterances = utterances

        def __eq__(self, other: object) -> bool:
            return isinstance(other, FakeRoute) and self.name == other.name

        def __repr__(self) -> str:
            return f"FakeRoute(name={self.name!r}, utterances={self.utterances!r})"

    mock_sr = MagicMock()
    mock_sr.Route = FakeRoute

    sys.modules.setdefault("semantic_router", mock_sr)
    sys.modules.setdefault("semantic_router.llms", MagicMock())
    sys.modules.setdefault("semantic_router.llms.base", MagicMock())
    sys.modules.setdefault("semantic_router.schema", MagicMock())
    sys.modules.setdefault("semantic_router.utils", MagicMock())
    sys.modules.setdefault("semantic_router.utils.logger", MagicMock())
    sys.modules.setdefault("semantic_router.encoders", MagicMock())
    sys.modules.setdefault("semantic_router.routers", MagicMock())
    sys.modules.setdefault("pydantic", MagicMock())
    sys.modules.setdefault("ollama", MagicMock())


try:
    import semantic_router  # noqa: F401
except ImportError:
    _install_semantic_router_mock()
