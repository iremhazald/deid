"""Tiny text helpers shared by detectors without importing the registry."""

from __future__ import annotations

import unicodedata


def fold_tr(value: str) -> str:
    """Case-fold Turkish text, flattening circumflex variants."""
    folded = unicodedata.normalize("NFC", value)
    for source, target in (("Â", "A"), ("Î", "I"), ("Û", "U"), ("â", "a"), ("î", "i"), ("û", "u")):
        folded = folded.replace(source, target)
    return folded.casefold()


def fold_tr_identity(value: str) -> str:
    """Turkish-aware identity fold: İ/I map correctly, i/ı collapse for matching."""
    mapped = unicodedata.normalize("NFKC", value).replace("İ", "i").replace("I", "ı")
    return fold_tr(mapped).replace("\u0307", "").replace("ı", "i")
