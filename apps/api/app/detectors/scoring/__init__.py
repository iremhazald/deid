"""Deterministic evidence scoring and candidate resolution.

Score is an evidence weight, not a probability or model confidence.
This package does not call LLMs, embeddings, or network APIs.
"""

from app.detectors.scoring.pipeline import apply_scoring

__all__ = ["apply_scoring"]
