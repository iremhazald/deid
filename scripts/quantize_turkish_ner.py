"""Create a separate INT8 copy of the published Turkish BERTurk ONNX NER model.

Development / maintenance only. Not invoked during user scans.

Source ``model.onnx`` is never overwritten. The default output is
``model.int8.onnx`` next to the FP32 artifact.

Requires the ``onnx`` package (used by ``onnxruntime.quantization``).
That package is not a runtime dependency of Local Context Scan.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_ID = "akdeniz27/bert-base-turkish-cased-ner"
DEFAULT_SOURCE_NAME = "model.onnx"
DEFAULT_OUTPUT_NAME = "model.int8.onnx"
QUANT_METHOD = "onnxruntime.quantization.quantize_dynamic"
QUANT_WEIGHT_TYPE = "QInt8"
QUANT_OP_TYPES = ("MatMul",)
_REQUIRED_INPUTS = ("input_ids", "attention_mask", "token_type_ids")
_REQUIRED_OUTPUT = "logits"


@dataclass(frozen=True)
class QuantizeResult:
    source: Path
    dest: Path
    source_bytes: int
    dest_bytes: int
    method: str
    weight_type: str
    op_types: tuple[str, ...]

    @property
    def reduction_pct(self) -> float:
        if self.source_bytes <= 0:
            return 0.0
        return (1.0 - (self.dest_bytes / self.source_bytes)) * 100.0


def _die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def resolve_default_fp32_path(model_id: str = DEFAULT_MODEL_ID) -> Path:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError as exc:
        raise FileNotFoundError(
            "huggingface_hub is required to locate the cached FP32 ONNX model."
        ) from exc
    cached = try_to_load_from_cache(model_id, DEFAULT_SOURCE_NAME)
    if not cached:
        raise FileNotFoundError(
            f"Cached {DEFAULT_SOURCE_NAME} was not found for {model_id}."
        )
    path = Path(str(cached))
    if not path.is_file():
        raise FileNotFoundError(f"Cached ONNX path is not a file: {path}")
    return path


def inspect_onnx(path: Path) -> dict[str, object]:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is required to inspect the ONNX artifact.") from exc
    disable = getattr(ort, "disable_telemetry_events", None)
    if callable(disable):
        disable()
    session = ort.InferenceSession(
        str(path),
        providers=["CPUExecutionProvider"],
    )
    inputs = [(item.name, item.type, list(item.shape)) for item in session.get_inputs()]
    outputs = [(item.name, item.type, list(item.shape)) for item in session.get_outputs()]
    return {
        "inputs": inputs,
        "outputs": outputs,
        "providers": list(session.get_providers()),
    }


def _assert_compatible_io(info: dict[str, object], *, label: str) -> None:
    input_names = {item[0] for item in info["inputs"]}  # type: ignore[index]
    output_names = {item[0] for item in info["outputs"]}  # type: ignore[index]
    missing = [name for name in _REQUIRED_INPUTS if name not in input_names]
    if missing or _REQUIRED_OUTPUT not in output_names:
        raise RuntimeError(
            f"{label} ONNX artifact has unexpected tensor names "
            f"(inputs={sorted(input_names)}, outputs={sorted(output_names)})."
        )
    logits = next(item for item in info["outputs"] if item[0] == _REQUIRED_OUTPUT)  # type: ignore[union-attr]
    last_dim = logits[2][-1] if logits[2] else None
    if last_dim not in {7, None, "num_labels"}:
        try:
            if int(last_dim) != 7:
                raise RuntimeError(
                    f"{label} ONNX logits width is {last_dim}, expected 7 NER labels."
                )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"{label} ONNX logits width is {last_dim}, expected 7 NER labels."
            ) from exc


def inspect_source_graph(path: Path) -> dict[str, int]:
    try:
        import onnx
    except ImportError as exc:
        raise RuntimeError(
            "The onnx package is required to inspect operators before quantization."
        ) from exc
    from collections import Counter

    model = onnx.load(str(path), load_external_data=False)
    counts = Counter(node.op_type for node in model.graph.node)
    return dict(counts)


def quantize_file(
    source: Path,
    dest: Path,
    *,
    overwrite: bool = False,
) -> QuantizeResult:
    source = source.resolve()
    dest = dest.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source ONNX file does not exist: {source}")
    if dest == source:
        raise ValueError("Refusing to overwrite the source ONNX file.")
    if dest.name == DEFAULT_SOURCE_NAME:
        raise ValueError(
            f"Refusing to write quantized weights as {DEFAULT_SOURCE_NAME}. "
            f"Use {DEFAULT_OUTPUT_NAME}."
        )
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Destination already exists: {dest}. Pass --force to replace the INT8 copy only."
        )

    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as exc:
        raise RuntimeError(
            "onnxruntime.quantization is unavailable. Install onnxruntime and the onnx package."
        ) from exc

    source_info = inspect_onnx(source)
    _assert_compatible_io(source_info, label="Source")
    op_counts = inspect_source_graph(source)
    missing_ops = [op for op in QUANT_OP_TYPES if op_counts.get(op, 0) <= 0]
    if missing_ops:
        raise RuntimeError(
            "Source ONNX graph does not contain quantizable operators "
            f"{missing_ops}. Refusing to invent an architecture change."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(
        model_input=str(source),
        model_output=str(dest),
        weight_type=QuantType.QInt8,
        op_types_to_quantize=list(QUANT_OP_TYPES),
        extra_options={"MatMulConstBOnly": True},
    )
    if not dest.is_file():
        raise RuntimeError(f"Quantization reported success but {dest} was not created.")

    dest_info = inspect_onnx(dest)
    _assert_compatible_io(dest_info, label="Quantized")

    return QuantizeResult(
        source=source,
        dest=dest,
        source_bytes=source.stat().st_size,
        dest_bytes=dest.stat().st_size,
        method=QUANT_METHOD,
        weight_type=QUANT_WEIGHT_TYPE,
        op_types=QUANT_OP_TYPES,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quantize the published Turkish BERTurk FP32 ONNX NER model to a separate INT8 file."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help=f"FP32 ONNX path (default: cached {DEFAULT_MODEL_ID} {DEFAULT_SOURCE_NAME})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"INT8 ONNX path (default: sibling {DEFAULT_OUTPUT_NAME})",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Hugging Face checkpoint id used only to locate the cached FP32 file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing INT8 file. Never overwrites the FP32 source.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        source = args.input.resolve() if args.input else resolve_default_fp32_path(args.model_id)
    except FileNotFoundError as exc:
        _die(str(exc))
    dest = args.output.resolve() if args.output else source.parent / DEFAULT_OUTPUT_NAME
    print(f"source={source}")
    print(f"source_bytes={source.stat().st_size}")
    print(f"method={QUANT_METHOD}")
    print(f"weight_type={QUANT_WEIGHT_TYPE}")
    print(f"op_types={','.join(QUANT_OP_TYPES)}")
    try:
        result = quantize_file(source, dest, overwrite=args.force)
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as exc:
        _die(str(exc))
    except Exception as exc:
        _die(f"Quantization failed: {exc}")
    print(f"dest={result.dest}")
    print(f"dest_bytes={result.dest_bytes}")
    print(f"reduction_pct={result.reduction_pct:.2f}")
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
