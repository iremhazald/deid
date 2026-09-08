"""Optional local NER candidate generation.

This package is a candidate generator only. It does not mask, validate
structured identifiers, or assign identity. Heavy ML imports stay inside
provider ``load()`` so Standard Scan never initializes a model.
"""

from app.domain.models import LocalNERStatus

from .models import (
    LocalNERLanguage,
    LocalNERProviderName,
    LocalNERRun,
    NERPrediction,
)

__all__ = [
    "LocalNERLanguage",
    "LocalNERProviderName",
    "LocalNERRun",
    "LocalNERStatus",
    "NERPrediction",
]
