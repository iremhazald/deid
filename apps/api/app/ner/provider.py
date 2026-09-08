"""Local NER provider contract and process-wide lazy cache.

Models are created on first use of that language only. Concurrent first
requests share one initialization lock per language.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from app.ner.models import NERPrediction


@runtime_checkable
class LocalNERProvider(Protocol):
    language: str
    provider_name: str
    model_id: str

    def load(self) -> None:
        """Initialize the model. Safe to call more than once."""
        ...

    def is_available(self) -> bool:
        """True when dependencies and local model assets can be used."""
        ...

    def predict(self, text: str, language: str) -> list[NERPrediction]:
        """Return offset-faithful predictions for ``text``."""
        ...

    def unload(self) -> None:
        """Release the cached model. Optional."""
        ...

    def metadata(self) -> dict[str, str]:
        """Safe provider metadata. No document text."""
        ...


class _CachedProvider:
    def __init__(self, factory) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._instance: LocalNERProvider | None = None

    def get(self) -> LocalNERProvider:
        if self._instance is not None:
            return self._instance
        with self._lock:
            instance = self._instance
            if instance is None:
                instance = self._factory()
                self._instance = instance
            return instance

    def peek(self) -> LocalNERProvider | None:
        return self._instance


class LocalNERRegistry:
    """Process-wide language → provider cache. Does not load on import."""

    def __init__(self) -> None:
        self._tr = _CachedProvider(self._make_turkish)
        self._en = _CachedProvider(self._make_english)

    @staticmethod
    def _make_turkish() -> LocalNERProvider:
        from app.ner.turkish import TurkishBerturkNERProvider

        return TurkishBerturkNERProvider()

    @staticmethod
    def _make_english() -> LocalNERProvider:
        from app.ner.english import EnglishSpacyNERProvider

        return EnglishSpacyNERProvider()

    def provider_for(self, language: str) -> LocalNERProvider:
        if language == "tr":
            return self._tr.get()
        if language == "en":
            return self._en.get()
        raise ValueError(f"unsupported local NER language: {language}")

    def cached(self, language: str) -> LocalNERProvider | None:
        if language == "tr":
            return self._tr.peek()
        if language == "en":
            return self._en.peek()
        return None

    def is_loaded(self, language: str) -> bool:
        provider = self.cached(language)
        return bool(provider is not None and getattr(provider, "loaded", False))


_REGISTRY = LocalNERRegistry()


def ner_registry() -> LocalNERRegistry:
    return _REGISTRY


def reset_ner_registry_for_tests() -> None:
    """Replace the process cache. Tests only."""
    global _REGISTRY
    _REGISTRY = LocalNERRegistry()
