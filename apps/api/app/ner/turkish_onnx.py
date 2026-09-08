"""ONNX Runtime backend for Turkish BERTurk token classification.

Heavy imports stay inside ``load()``. This module never imports torch and
never constructs a Transformers model or pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.ner.models import LocalNERError, LocalNERErrorCode
from app.ner.turkish_decode import decode_token_classification, softmax_logits

ONNX_WEIGHTS_NAME = "model.onnx"
INT8_WEIGHTS_NAME = "model.int8.onnx"
DEFAULT_ONNX_VARIANT = "fp32"
_ALLOWED_ONNX_VARIANTS = frozenset({"fp32", "int8"})
_VARIANT_TO_FILENAME = {
    "fp32": ONNX_WEIGHTS_NAME,
    "int8": INT8_WEIGHTS_NAME,
}
_REQUIRED_INPUTS = ("input_ids", "attention_mask", "token_type_ids")
_REQUIRED_OUTPUT = "logits"
_REQUIRED_TYPES = frozenset({"PER", "ORG", "LOC"})


def normalize_tr_ner_onnx_variant(raw: str | None) -> str:
    value = (raw or DEFAULT_ONNX_VARIANT).strip().lower()
    if value not in _ALLOWED_ONNX_VARIANTS:
        return ""
    return value


def onnx_filename_for_variant(variant: str) -> str:
    return _VARIANT_TO_FILENAME.get(variant, "")


def _resolve_cached_file(model_id: str, filename: str) -> Path | None:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None
    try:
        path = try_to_load_from_cache(model_id, filename)
    except Exception:
        return None
    if path is None:
        return None
    resolved = Path(str(path))
    if not resolved.is_file():
        return None
    return resolved


def cached_onnx_assets_available(
    model_id: str, filename: str = ONNX_WEIGHTS_NAME
) -> bool:
    if not filename:
        return False
    config = _resolve_cached_file(model_id, "config.json")
    if config is None:
        return False
    onnx_path = config.parent / filename
    if onnx_path.is_file():
        return True
    return _resolve_cached_file(model_id, filename) is not None


def resolve_onnx_path(
    model_id: str,
    *,
    local_only: bool,
    filename: str = ONNX_WEIGHTS_NAME,
    allow_download: bool | None = None,
) -> Path:
    if not filename:
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            "Turkish NER ONNX variant is not recognized.",
        )
    if allow_download is None:
        allow_download = filename == ONNX_WEIGHTS_NAME
    config = _resolve_cached_file(model_id, "config.json")
    if config is not None:
        sibling = config.parent / filename
        if sibling.is_file():
            return sibling
    cached = _resolve_cached_file(model_id, filename)
    if cached is not None:
        return cached
    if local_only or not allow_download:
        if filename == INT8_WEIGHTS_NAME:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
                "Turkish NER INT8 ONNX weights are not available locally. "
                "Generate model.int8.onnx with scripts/quantize_turkish_ner.py.",
            )
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            "Turkish NER ONNX weights are not available locally. "
            "Cache model.onnx for the configured checkpoint before Local Context Scan.",
        )
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
            "Turkish local NER requires huggingface_hub to resolve ONNX weights.",
        ) from exc
    try:
        downloaded = hf_hub_download(model_id, filename)
    except Exception as exc:
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            "Turkish NER ONNX weights could not be downloaded.",
        ) from exc
    path = Path(downloaded)
    if not path.is_file():
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            "Turkish NER ONNX weights are not available locally. "
            "Cache model.onnx for the configured checkpoint before Local Context Scan.",
        )
    return path


def _id2label_from_config(config: Any) -> dict[int, str]:
    raw = getattr(config, "id2label", None)
    if not raw:
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
            "Turkish NER checkpoint config does not define id2label.",
        )
    mapping: dict[int, str] = {}
    for key, value in dict(raw).items():
        try:
            mapping[int(key)] = str(value)
        except (TypeError, ValueError) as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER checkpoint id2label is not usable.",
            ) from exc
    present = {label.split("-", 1)[-1] for label in mapping.values() if label != "O"}
    if not _REQUIRED_TYPES.issubset(present):
        raise LocalNERError(
            LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
            "Turkish NER checkpoint does not publish PER / ORG / LOC labels.",
        )
    return mapping


class TurkishOnnxBackend:
    """CPU ONNX Runtime inference. Session is created only by ``load()``."""

    def __init__(
        self,
        model_id: str,
        *,
        local_only: bool,
        onnx_variant: str = DEFAULT_ONNX_VARIANT,
    ) -> None:
        self.model_id = model_id
        self._local_only = local_only
        self.onnx_variant = normalize_tr_ner_onnx_variant(onnx_variant)
        self.onnx_filename = onnx_filename_for_variant(self.onnx_variant)
        self.tokenizer: Any = None
        self.runtime: Any = None
        self.id2label: dict[int, str] = {}
        self._input_names: set[str] = set()
        self._max_length = 512

    def load(self) -> None:
        try:
            import onnxruntime as ort
            from transformers import AutoConfig, AutoTokenizer
        except ImportError as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                "Turkish local NER requires the local-ner-tr extra "
                "(transformers + onnxruntime).",
            ) from exc

        disable_telemetry = getattr(ort, "disable_telemetry_events", None)
        if callable(disable_telemetry):
            disable_telemetry()

        if not self.onnx_variant or not self.onnx_filename:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX variant must be 'fp32' or 'int8'.",
            )
        onnx_path = resolve_onnx_path(
            self.model_id,
            local_only=self._local_only,
            filename=self.onnx_filename,
            allow_download=self.onnx_variant == "fp32",
        )
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, local_files_only=self._local_only
            )
            config = AutoConfig.from_pretrained(
                self.model_id, local_files_only=self._local_only
            )
        except OSError as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
                "Turkish NER tokenizer or config is not available locally. "
                "Install/cache the configured checkpoint before Local Context Scan.",
            ) from exc
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER tokenizer failed to load.",
            ) from exc
        if not getattr(tokenizer, "is_fast", False):
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER requires a fast tokenizer for offset mapping.",
            )
        id2label = _id2label_from_config(config)

        options = ort.SessionOptions()
        # Conservative defaults: no intra/inter-op thread override.
        try:
            session = ort.InferenceSession(
                str(onnx_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX session failed to load.",
            ) from exc

        input_names = {item.name for item in session.get_inputs()}
        output_names = {item.name for item in session.get_outputs()}
        missing = [name for name in _REQUIRED_INPUTS if name not in input_names]
        if missing or _REQUIRED_OUTPUT not in output_names:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX artifact has unexpected tensor names.",
            )
        logits_info = next(item for item in session.get_outputs() if item.name == _REQUIRED_OUTPUT)
        last_dim = logits_info.shape[-1] if logits_info.shape else None
        if last_dim not in {len(id2label), None, "num_labels"}:
            try:
                if int(last_dim) != len(id2label):
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                        "Turkish NER ONNX logits width does not match id2label.",
                    )
            except (TypeError, ValueError):
                pass

        model_max = int(getattr(tokenizer, "model_max_length", 0) or 0)
        config_max = int(getattr(config, "max_position_embeddings", 0) or 0)
        self._max_length = min(value for value in (model_max, config_max, 512) if value > 0) or 512
        self.tokenizer = tokenizer
        self.runtime = session
        self.id2label = id2label
        self._input_names = input_names

    def infer(self, text: str) -> list[dict[str, Any]]:
        if self.runtime is None or self.tokenizer is None:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX session is not loaded.",
            )
        try:
            encoded = self.tokenizer(
                text,
                truncation=True,
                max_length=self._max_length,
                padding=False,
                return_offsets_mapping=True,
                return_special_tokens_mask=True,
            )
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER tokenizer failed.",
            ) from exc
        offsets = encoded.get("offset_mapping")
        special = encoded.get("special_tokens_mask")
        if not offsets or special is None:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER tokenizer did not provide offset mappings.",
            )

        input_ids = np.ascontiguousarray([encoded["input_ids"]], dtype=np.int64)
        attention_mask = np.ascontiguousarray([encoded["attention_mask"]], dtype=np.int64)
        if "token_type_ids" in encoded:
            token_type_ids = np.ascontiguousarray([encoded["token_type_ids"]], dtype=np.int64)
        else:
            token_type_ids = np.zeros_like(input_ids, dtype=np.int64)
        feeds = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        }
        try:
            logits = self.runtime.run([_REQUIRED_OUTPUT], feeds)[0]
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER inference failed.",
            ) from exc
        if not isinstance(logits, np.ndarray) or logits.ndim != 3:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX output is not a logits tensor.",
            )
        if logits.shape[-1] != len(self.id2label):
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "Turkish NER ONNX logits width does not match id2label.",
            )
        scores = softmax_logits(logits[0])
        return decode_token_classification(
            text,
            scores=scores,
            offset_mapping=offsets,
            special_tokens_mask=special,
            id2label=self.id2label,
        )
