"""BERTurk token-classification provider. Heavy imports stay inside load()."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.config import get_settings
from app.ner.chunking import predict_chunked
from app.ner.instrumentation import timed_ms
from app.ner.labels import mapped_entity_type
from app.ner.models import LocalNERError, LocalNERErrorCode, NERPrediction

logger = logging.getLogger(__name__)

DEFAULT_TR_NER_MODEL = "akdeniz27/bert-base-turkish-cased-ner"
DEFAULT_TR_NER_BACKEND = "onnx"
DEFAULT_TR_NER_ONNX_VARIANT = "fp32"
_ALLOWED_BACKENDS = frozenset({"onnx", "pytorch"})
_ALLOWED_ONNX_VARIANTS = frozenset({"fp32", "int8"})
_MAX_TOKENS = 384
_STRIDE_TOKENS = 64


def _spec_available(*names: str) -> bool:
    import importlib.util

    return all(importlib.util.find_spec(name) is not None for name in names)


def _onnx_stack_installed() -> bool:
    return _spec_available("transformers", "onnxruntime", "numpy")


def _pytorch_stack_installed() -> bool:
    return _spec_available("transformers", "torch")


def _cached_model_path(model_id: str, filename: str = "config.json") -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    try:
        path = try_to_load_from_cache(model_id, filename)
    except Exception:
        return False
    if not path:
        return False
    from pathlib import Path

    return Path(str(path)).is_file()


def normalize_tr_ner_backend(raw: str | None) -> str:
    value = (raw or DEFAULT_TR_NER_BACKEND).strip().lower()
    if value not in _ALLOWED_BACKENDS:
        return ""
    return value


def normalize_tr_ner_onnx_variant(raw: str | None) -> str:
    value = (raw or DEFAULT_TR_NER_ONNX_VARIANT).strip().lower()
    if value not in _ALLOWED_ONNX_VARIANTS:
        return ""
    return value


class TurkishBerturkNERProvider:
    language = "tr"
    provider_name = "BERTURK"

    def __init__(
        self,
        model_id: str | None = None,
        backend: str | None = None,
        onnx_variant: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model_id = model_id or settings.deid_tr_ner_model
        self.backend_name = normalize_tr_ner_backend(
            backend if backend is not None else getattr(settings, "deid_tr_ner_backend", None)
        )
        self.onnx_variant = normalize_tr_ner_onnx_variant(
            onnx_variant
            if onnx_variant is not None
            else getattr(settings, "deid_tr_ner_onnx_variant", None)
        )
        self._local_only = settings.deid_ner_local_files_only
        self._max_chars = settings.deid_ner_max_chars_per_chunk
        self._chunk_overlap = settings.deid_ner_chunk_overlap_chars
        self._lock = threading.Lock()
        self._backend: Any = None
        self._tokenizer: Any = None
        self._runtime: Any = None
        self.loaded = False
        self.last_load_ms: float | None = None

    def metadata(self) -> dict[str, str]:
        meta = {
            "language": self.language,
            "provider": self.provider_name,
            "model_id": self.model_id,
            "backend": self.backend_name or "unknown",
        }
        if self.backend_name == "onnx":
            meta["onnx_variant"] = self.onnx_variant or "unknown"
        return meta

    def is_available(self) -> bool:
        if not self.backend_name:
            return False
        if self.loaded:
            return True
        if self.backend_name == "onnx":
            if not self.onnx_variant:
                return False
            if not _onnx_stack_installed():
                return False
            from app.ner.turkish_onnx import (
                cached_onnx_assets_available,
                onnx_filename_for_variant,
            )

            filename = onnx_filename_for_variant(self.onnx_variant)
            if self.onnx_variant == "int8":
                # Generated local artifact only. Never treat INT8 as downloadable.
                return cached_onnx_assets_available(self.model_id, filename)
            if self._local_only:
                return cached_onnx_assets_available(self.model_id, filename)
            return True
        if not _pytorch_stack_installed():
            return False
        if self._local_only:
            return _cached_model_path(self.model_id)
        return True

    def unload(self) -> None:
        with self._lock:
            self._backend = None
            self._tokenizer = None
            self._runtime = None
            self.loaded = False

    def load(self) -> None:
        if self.loaded and self._backend is not None:
            return
        with self._lock:
            if self.loaded and self._backend is not None:
                return
            if not self.backend_name:
                raise LocalNERError(
                    LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                    "Turkish local NER backend must be 'onnx' or 'pytorch'.",
                )
            if self.backend_name == "onnx":
                if not self.onnx_variant:
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                        "Turkish NER ONNX variant must be 'fp32' or 'int8'.",
                    )
                if not _onnx_stack_installed():
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                        "Turkish local NER requires the local-ner-tr extra "
                        "(transformers + onnxruntime).",
                    )
                from app.ner.turkish_onnx import TurkishOnnxBackend

                backend: Any = TurkishOnnxBackend(
                    self.model_id,
                    local_only=self._local_only,
                    onnx_variant=self.onnx_variant,
                )
            else:
                if not _pytorch_stack_installed():
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                        "Turkish PyTorch NER requires transformers and torch.",
                    )
                from app.ner.turkish_pytorch import TurkishPytorchBackend

                backend = TurkishPytorchBackend(
                    self.model_id, local_only=self._local_only
                )
            with timed_ms() as elapsed:
                backend.load()
            self._backend = backend
            self._tokenizer = backend.tokenizer
            self._runtime = backend.runtime
            self.loaded = True
            self.last_load_ms = elapsed[0]
            logger.info(
                "local_ner loaded provider=BERTURK backend=%s load_ms=%.1f",
                self.backend_name,
                self.last_load_ms,
            )

    def predict(self, text: str, language: str) -> list[NERPrediction]:
        if language != "tr":
            return []
        if not text:
            return []
        self.load()
        return predict_chunked(
            text,
            self._predict_window,
            max_chars=self._max_chars,
            overlap=self._chunk_overlap,
        )

    def _predict_window(self, text: str) -> list[NERPrediction]:
        assert self._backend is not None
        windows = self._token_windows(text)
        found: list[NERPrediction] = []
        for window_text, origin in windows:
            try:
                raw_items = self._backend.infer(window_text)
            except LocalNERError:
                raise
            except Exception as exc:
                raise LocalNERError(
                    LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                    "Turkish NER inference failed.",
                ) from exc
            for item in raw_items:
                prediction = self._from_pipeline_item(item, window_text, origin)
                if prediction is not None:
                    found.append(prediction)
        return found

    def _token_windows(self, text: str) -> list[tuple[str, int]]:
        tokenizer = self._tokenizer
        if tokenizer is None or not text:
            return [(text, 0)]
        try:
            encoding = tokenizer(
                text,
                return_offsets_mapping=True,
                return_overflowing_tokens=True,
                stride=_STRIDE_TOKENS,
                max_length=_MAX_TOKENS,
                truncation=True,
                padding=False,
            )
        except Exception:
            return [(text, 0)]
        offsets_all = encoding.get("offset_mapping")
        if not offsets_all:
            return [(text, 0)]
        # Single sequence (no overflow) still arrives as one offset list.
        if offsets_all and isinstance(offsets_all[0], tuple):
            windows = [offsets_all]
        else:
            windows = offsets_all
        result: list[tuple[str, int]] = []
        seen: set[int] = set()
        for offsets in windows:
            char_starts = [start for start, end in offsets if end > start]
            char_ends = [end for start, end in offsets if end > start]
            if not char_starts or not char_ends:
                continue
            origin = char_starts[0]
            finish = char_ends[-1]
            if origin in seen:
                continue
            seen.add(origin)
            result.append((text[origin:finish], origin))
        return result or [(text, 0)]

    def _from_pipeline_item(
        self, item: dict[str, Any], window: str, origin: int
    ) -> NERPrediction | None:
        label = str(item.get("entity_group") or item.get("entity") or "")
        if mapped_entity_type(label) is None:
            return None
        try:
            start = int(item["start"])
            end = int(item["end"])
        except (KeyError, TypeError, ValueError):
            return None
        if start < 0 or end > len(window) or end <= start:
            return None
        surface = window[start:end]
        if not surface.strip():
            return None
        score = item.get("score")
        try:
            numeric = float(score) if score is not None else None
        except (TypeError, ValueError):
            numeric = None
        return NERPrediction(
            start=start + origin,
            end=end + origin,
            text=surface,
            label=label,
            score=numeric,
            language=self.language,
            provider=self.provider_name,
            model_id=self.model_id,
        )
