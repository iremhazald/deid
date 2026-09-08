"""Isolated PyTorch fallback for Turkish BERTurk NER.

Imported only when ``DEID_TR_NER_BACKEND=pytorch``. Never used as a silent
fallback from the ONNX path.
"""

from __future__ import annotations

from typing import Any

from app.ner.models import LocalNERError, LocalNERErrorCode


class TurkishPytorchBackend:
    def __init__(self, model_id: str, *, local_only: bool) -> None:
        self.model_id = model_id
        self._local_only = local_only
        self.tokenizer: Any = None
        self.runtime: Any = None

    def load(self) -> None:
        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline
        except ImportError as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                "Turkish PyTorch NER requires transformers and torch.",
            ) from exc
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, local_files_only=self._local_only
            )
            model = AutoModelForTokenClassification.from_pretrained(
                self.model_id, local_files_only=self._local_only
            )
            self.runtime = pipeline(
                "token-classification",
                model=model,
                tokenizer=tokenizer,
                aggregation_strategy="simple",
                device=-1,
            )
            self.tokenizer = tokenizer
        except OSError as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
                "Turkish NER model files are not available locally. "
                "Install/cache the configured checkpoint before Local Context Scan.",
            ) from exc
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER model failed to load.",
            ) from exc

    def infer(self, text: str) -> list[dict[str, Any]]:
        if self.runtime is None:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER pipeline is not loaded.",
            )
        try:
            raw_items = self.runtime(text)
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER inference failed.",
            ) from exc
        return list(raw_items)
