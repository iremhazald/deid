"""Offline Turkish case-suffix attachment and conservative inflection stripping.

Legal names in Turkish are typically written with an apostrophe plus a case
ending (``Yılmaz'ın``, ``Demir'e``, ``Özkan'da``). Replacing the name with a
placeholder must keep that ending, but the vowels (and the ``d/t`` locative
choice) have to follow the *replacement* stem:

    Mehmet Yılmaz'ın  →  [KİŞİ_1]'in     (KİŞİ: last vowel İ → front)
    [SANIK_1]  + ın   →  [SANIK_1]'ın    (SANIK: last vowel I/ı → back)

This module is a *morphological helper*, not a detector:

- It does not emit PERSON_NAME (or any) detections.
- It does not discover new names, assign legal roles, or resolve identity.
- It only analyses the Turkish inflection of a surface that some other
  component already treated as an entity / user term.

Zemberek-NLP (``zemberek-python``) is optional. Local closed-set logic always
runs first. Zemberek is a fallback for leftovers the closed set does not know,
and never generates placeholder surfaces (those are not in any lexicon).
``zemberek-python`` also cannot share an environment with RapidOCR
(it pins ``antlr4-python3-runtime==4.8``).

The engine never calls a network API.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Turkish-aware vowel fold. ASCII ``I`` in uppercase Turkish is ``ı``, not ``i``.
_VOWEL_FOLD: dict[str, str] = {
    "a": "a",
    "A": "a",
    "â": "a",
    "Â": "a",
    "e": "e",
    "E": "e",
    "ê": "e",
    "Ê": "e",
    "ı": "ı",
    "I": "ı",
    "i": "i",
    "İ": "i",
    "î": "i",
    "Î": "i",
    "o": "o",
    "O": "o",
    "ô": "o",
    "Ô": "o",
    "ö": "ö",
    "Ö": "ö",
    "u": "u",
    "U": "u",
    "û": "u",
    "Û": "u",
    "ü": "ü",
    "Ü": "ü",
}
_FRONT = frozenset("eiöüêî")
_ROUNDED = frozenset("oöuüôû")
_VOICELESS = frozenset("fstkçşhpFSTKÇŞHP")
_WORD_VOWELS = frozenset(_VOWEL_FOLD)
_APOSTROPHES = "'’′"
_APOSTROPHE_SUFFIX_AT_START = re.compile(
    r"(?:'|\u2019|\u2032)([^\s.,;:!?]+)"
)
_BRACKET_TOKEN = re.compile(r"^\[[^\]]+\]$")
_SURFACE_SPLIT = re.compile(
    r"^(?P<base>.+?)['’\u2019\u2032](?P<suffix>[A-Za-zçğıöşüâîûÇĞİÖŞÜ]+)$"
)
_MAX_SUFFIX_LETTERS = 12


class SuffixKind(str, Enum):
    """Turkish nominal case (or leftover) carried after a name."""

    GENITIVE = "genitive"  # tamlayan / iyelik artığı: ın/in/un/ün
    DATIVE = "dative"  # yönelme: a/e
    LOCATIVE = "locative"  # bulunma: da/de/ta/te
    ABLATIVE = "ablative"  # çıkma: dan/den/tan/ten
    ACCUSATIVE = "accusative"  # belirtme: ı/i/u/ü
    INSTRUMENTAL = "instrumental"  # vasıta: la/le/yla/yle
    RELATIVE = "relative"  # ki
    LOCATIVE_RELATIVE = "locative_relative"  # daki/deki/…
    UNKNOWN = "unknown"


SourceKind = Literal["local", "zemberek", "none"]


@dataclass(frozen=True)
class InflectedSurface:
    """Morphological split of an already-detected surface. Not an identity claim."""

    surface: str
    base: str
    suffix: str
    apostrophe_suffix: str
    kind: SuffixKind
    source: SourceKind


_ZEMBEREK_CASE = {
    "Gen": SuffixKind.GENITIVE,
    "Dat": SuffixKind.DATIVE,
    "Loc": SuffixKind.LOCATIVE,
    "Abl": SuffixKind.ABLATIVE,
    "Acc": SuffixKind.ACCUSATIVE,
    "Ins": SuffixKind.INSTRUMENTAL,
    "Rel": SuffixKind.RELATIVE,
}

_SUFFIX_GROUPS: dict[SuffixKind, frozenset[str]] = {
    SuffixKind.GENITIVE: frozenset({"ın", "in", "un", "ün", "nın", "nin", "nun", "nün"}),
    SuffixKind.DATIVE: frozenset({"a", "e", "ya", "ye", "na", "ne"}),
    SuffixKind.LOCATIVE: frozenset({"da", "de", "ta", "te", "nda", "nde"}),
    SuffixKind.ABLATIVE: frozenset({"dan", "den", "tan", "ten", "ndan", "nden"}),
    SuffixKind.ACCUSATIVE: frozenset(
        {"ı", "i", "u", "ü", "yı", "yi", "yu", "yü", "nı", "ni", "nu", "nü"}
    ),
    SuffixKind.INSTRUMENTAL: frozenset({"la", "le", "yla", "yle"}),
    SuffixKind.RELATIVE: frozenset({"ki"}),
    SuffixKind.LOCATIVE_RELATIVE: frozenset(
        {"daki", "deki", "taki", "teki", "ndaki", "ndeki"}
    ),
}

# Grouping always strips these, Zemberek or not. Matches the pre-existing
# closed set so ``Mehmet Yılmaz'ın`` keeps grouping when morphology is absent.
_GROUPING_SUFFIXES: frozenset[str] = frozenset().union(
    _SUFFIX_GROUPS[SuffixKind.GENITIVE],
    _SUFFIX_GROUPS[SuffixKind.DATIVE],
    _SUFFIX_GROUPS[SuffixKind.LOCATIVE],
    _SUFFIX_GROUPS[SuffixKind.ABLATIVE],
    _SUFFIX_GROUPS[SuffixKind.ACCUSATIVE],
)

# Deterministic extras for suffix *copy* / custom-term expansion. Not used for
# person grouping unless Zemberek independently confirms the same split.
_EXTENDED_SUFFIXES: frozenset[str] = frozenset().union(
    _SUFFIX_GROUPS[SuffixKind.INSTRUMENTAL],
    _SUFFIX_GROUPS[SuffixKind.RELATIVE],
    _SUFFIX_GROUPS[SuffixKind.LOCATIVE_RELATIVE],
)

_ALL_LOCAL_SUFFIXES: frozenset[str] = _GROUPING_SUFFIXES | _EXTENDED_SUFFIXES

_SUFFIX_KIND_BY_FORM: dict[str, SuffixKind] = {
    form: kind for kind, forms in _SUFFIX_GROUPS.items() for form in forms
}

_morphology: Any | None = None
_morphology_failed = False
_morphology_lock = threading.Lock()


def zemberek_available() -> bool:
    """Return True when zemberek-python can be imported in this environment."""
    try:
        from importlib.util import find_spec

        return find_spec("zemberek") is not None
    except Exception:
        return False


def _get_zemberek_morphology() -> Any | None:
    """Lazy singleton. First load reads lexicons; later calls are cheap."""
    global _morphology, _morphology_failed
    if _morphology is not None:
        return _morphology
    if _morphology_failed:
        return None
    with _morphology_lock:
        if _morphology is not None:
            return _morphology
        if _morphology_failed:
            return None
        try:
            from importlib import import_module

            morphology_cls = getattr(import_module("zemberek"), "TurkishMorphology")
            _morphology = morphology_cls.create_with_defaults()
            return _morphology
        except Exception as exc:
            _morphology_failed = True
            logger.info("Zemberek morphology unavailable; using local harmony. (%s)", exc)
            return None


def clear_morphology_caches() -> None:
    """Drop per-token analyze cache. Used by tests after monkeypatching."""
    _zemberek_analyze_cached.cache_clear()


def last_vowel(value: str) -> str | None:
    """Return the last Turkish vowel of ``value``, folded to lowercase.

    ``I`` (U+0049) is treated as ``ı`` and ``İ`` (U+0130) as ``i``, which is
    the uppercase Turkish convention. Digits, brackets and punctuation are
    skipped so ``[SANIK_1]`` yields ``ı`` and ``[KİŞİ_1]`` yields ``i``.
    """
    for char in reversed(value):
        folded = _VOWEL_FOLD.get(char)
        if folded is not None:
            return folded
    return None


def _last_letter(value: str) -> str:
    """Last alphabetic character, ignoring digits/brackets/underscores."""
    for char in reversed(value):
        if char.isalpha():
            return char
    return value[-1:] if value else ""


def _fold_suffix(raw: str) -> str:
    folded = unicodedata.normalize("NFKC", raw).strip().lstrip(_APOSTROPHES)
    mapped = folded.replace("İ", "i").replace("I", "ı")
    return mapped.casefold().replace("\u0307", "")


def _local_kind(raw_suffix: str) -> SuffixKind | None:
    form = _fold_suffix(raw_suffix)
    if not form or len(form) > _MAX_SUFFIX_LETTERS:
        return None
    return _SUFFIX_KIND_BY_FORM.get(form)


def classify_suffix(raw_suffix: str, original_token: str | None = None) -> SuffixKind:
    """Identify the case of a leftover apostrophe suffix.

    Order is regex/local first, Zemberek second. Known legal leftovers such as
    ``ın`` / ``e`` / ``da`` must not change just because Zemberek is present.
    """
    local = _local_kind(raw_suffix)
    if local is not None:
        return local
    if original_token:
        kind = _classify_with_zemberek(original_token)
        if kind is not None and kind != SuffixKind.UNKNOWN:
            return kind
    if raw_suffix:
        probe = f"Ahmet'{_fold_suffix(raw_suffix) or raw_suffix.lstrip(_APOSTROPHES)}"
        kind = _classify_with_zemberek(probe)
        if kind is not None and kind != SuffixKind.UNKNOWN:
            return kind
    return SuffixKind.UNKNOWN


def suffix_classification_token(surface: str, raw_suffix: str) -> str | None:
    """Last token Zemberek should see when classifying ``raw_suffix``.

    Prefers the real last word (``Yılmaz'ın``) over a synthetic ``Ahmet'ın``.
    """
    suffix = _fold_suffix(raw_suffix)
    if not suffix:
        return None
    parts = unicodedata.normalize("NFKC", surface).strip().split()
    last = parts[-1] if parts else surface.strip()
    if not last:
        return None
    if any(mark in last for mark in _APOSTROPHES):
        return last
    return f"{last}'{suffix}"


def _classify_with_zemberek(token: str) -> SuffixKind | None:
    parsed = _zemberek_token_parse(token)
    if parsed is None:
        return None
    return parsed[0]


def _zemberek_token_parse(token: str) -> tuple[SuffixKind, str] | None:
    """Parse one token. Does not cache misses caused by a missing library."""
    if _get_zemberek_morphology() is None:
        return None
    return _zemberek_analyze_cached(token)


@lru_cache(maxsize=4096)
def _zemberek_analyze_cached(token: str) -> tuple[SuffixKind, str] | None:
    """Cached analyze of one already-detected token. First load is the singleton."""
    morphology = _get_zemberek_morphology()
    if morphology is None:
        return None
    try:
        results = morphology.analyze(token)
    except Exception as exc:
        logger.debug("Zemberek analyze failed for %r: %s", token, exc)
        return None
    if not results:
        return None

    kinds: set[SuffixKind] = set()
    stems: list[str] = []
    for result in results:
        kind, stem = _parse_single_analysis(result)
        if kind is None:
            continue
        kinds.add(kind)
        if stem:
            stems.append(stem)
    if len(kinds) != 1:
        # Ambiguous or empty: never guess. False merge is worse than a miss.
        return None
    stem = stems[0] if stems else ""
    if stems and len({_fold_suffix(item) for item in stems if item}) > 1:
        return None
    return next(iter(kinds)), stem


def _parse_single_analysis(result: Any) -> tuple[SuffixKind | None, str]:
    stem = _analysis_stem(result)
    found: set[SuffixKind] = set()
    try:
        morphemes = result.get_morphemes()
    except Exception:
        formatted = str(result)
        for code, kind in _ZEMBEREK_CASE.items():
            if f":{code}" in formatted or f"+{code}" in formatted or formatted.endswith(code):
                found.add(kind)
        if len(found) == 1:
            return next(iter(found)), stem
        return None, stem
    for morpheme in morphemes:
        code = str(getattr(morpheme, "id_", "") or getattr(morpheme, "id", "") or "")
        kind = _ZEMBEREK_CASE.get(code)
        if kind is not None:
            found.add(kind)
    if len(found) == 1:
        return next(iter(found)), stem
    return None, stem


def _analysis_stem(result: Any) -> str:
    for name in ("get_stem", "get_lem", "get_lexical_item"):
        getter = getattr(result, name, None)
        if not callable(getter):
            continue
        try:
            value = getter()
        except Exception:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        lemma = getattr(value, "lemma", None) or getattr(value, "root", None)
        if isinstance(lemma, str) and lemma.strip():
            return lemma.strip()
    formatted = str(result)
    if ":" in formatted:
        return formatted.split(":", 1)[0].strip()
    return ""


def analyze_inflected_surface(
    surface: str,
    *,
    allow_extended_local: bool = False,
    allow_zemberek: bool = False,
) -> InflectedSurface:
    """Split ``Name'suffix`` when the leftover is a safe Turkish inflection.

    Local closed-set matching always wins. Zemberek is only consulted for
    leftovers that list does not cover, and only when ``allow_zemberek`` is set.
    Ambiguous analyses return an unstripped surface.
    """
    raw = unicodedata.normalize("NFKC", surface).strip()
    empty = InflectedSurface(
        surface=raw,
        base=raw,
        suffix="",
        apostrophe_suffix="",
        kind=SuffixKind.UNKNOWN,
        source="none",
    )
    match = _SURFACE_SPLIT.fullmatch(raw)
    if not match:
        return empty
    suffix_raw = match.group("suffix")
    if len(suffix_raw) > _MAX_SUFFIX_LETTERS:
        return empty
    form = _fold_suffix(suffix_raw)
    mark = raw[match.start("suffix") - 1]
    apostrophe_suffix = f"{mark}{suffix_raw}"
    base = match.group("base").strip()
    local_kind = _SUFFIX_KIND_BY_FORM.get(form)
    local_ok = form in _GROUPING_SUFFIXES or (
        allow_extended_local and form in _EXTENDED_SUFFIXES
    )
    if local_ok and local_kind is not None:
        return InflectedSurface(
            surface=raw,
            base=base,
            suffix=form,
            apostrophe_suffix=apostrophe_suffix,
            kind=local_kind,
            source="local",
        )
    if not allow_zemberek:
        return empty
    last = raw.split()[-1]
    parsed = _zemberek_token_parse(last)
    if parsed is None:
        return empty
    kind, stem = parsed
    if kind == SuffixKind.UNKNOWN:
        return empty
    expected = last.split(mark)[0]
    if stem and not _stem_matches(expected, stem):
        return empty
    return InflectedSurface(
        surface=raw,
        base=base,
        suffix=form,
        apostrophe_suffix=apostrophe_suffix,
        kind=kind,
        source="zemberek",
    )


def _stem_matches(surface_head: str, stem: str) -> bool:
    left = _fold_suffix(surface_head)
    right = _fold_suffix(stem)
    return bool(left) and left == right


def strip_inflection_if_safe(
    surface: str,
    *,
    require_multi_token_base: bool = True,
) -> str:
    """Return the uninflected base of an *already detected* person surface.

    This is normalized-text grouping, not coreference: ``Mehmet Yılmaz'ın``
    and ``Mehmet Yılmaz`` may share a key; ``Mehmet`` and ``M. Yılmaz`` never
    collapse into that key from this function.
    """
    parsed = analyze_inflected_surface(
        surface,
        allow_extended_local=False,
        allow_zemberek=True,
    )
    if parsed.source == "none" or not parsed.suffix:
        return surface.strip()
    base = parsed.base
    if require_multi_token_base and len(base.split()) < 2:
        return surface.strip()
    return base


def is_safe_custom_term_suffix(raw_suffix: str) -> bool:
    """True when a leftover after a *user-provided* term is a known inflection."""
    form = _fold_suffix(raw_suffix)
    return form in _ALL_LOCAL_SUFFIXES


def _high_vowel(vowel: str) -> str:
    front = vowel in _FRONT
    rounded = vowel in _ROUNDED
    if front and rounded:
        return "ü"
    if rounded:
        return "u"
    if front:
        return "i"
    return "ı"


def _low_vowel(vowel: str) -> str:
    return "e" if vowel in _FRONT else "a"


def _voiceless_ending(stem: str) -> bool:
    letter = _last_letter(stem)
    return letter.casefold() in {char.casefold() for char in _VOICELESS}


def _vowel_ending(stem: str) -> bool:
    letter = _last_letter(stem)
    return letter in _WORD_VOWELS or letter in _VOWEL_FOLD


def _skip_glide_buffer(stem: str) -> bool:
    """Bracket tokens are treated as codes: ``[KİŞİ_1]'in``, never ``'nin``."""
    return bool(_BRACKET_TOKEN.match(stem.strip()))


def inflect_case(
    stem: str,
    kind: SuffixKind,
    *,
    apostrophe: bool = True,
    original_suffix: str = "",
) -> str:
    """Build ``stem`` + (optional apostrophe) + harmonized ending.

    Glide consonants (``n`` / ``y``) follow the *replacement* stem, not the
    original name. Bracket placeholders never take a glide, matching legal-label
    convention (``[KİŞİ_1]'in``, never ``'nin``). Locative/ablative ``d`` vs
    ``t`` is recomputed from the new stem's last consonant.
    """
    if kind == SuffixKind.UNKNOWN:
        suffix = original_suffix.lstrip(_APOSTROPHES)
        if not suffix:
            return stem
        return f"{stem}'{suffix}" if apostrophe else f"{stem}{suffix}"

    vowel = last_vowel(stem) or "a"
    skip_glide = _skip_glide_buffer(stem)
    vowel_final = _vowel_ending(stem) and not skip_glide
    use_n_glide = vowel_final
    use_y_glide = vowel_final

    if kind == SuffixKind.GENITIVE:
        ending = ("n" if use_n_glide else "") + _high_vowel(vowel) + "n"
    elif kind == SuffixKind.DATIVE:
        ending = ("y" if use_y_glide else "") + _low_vowel(vowel)
    elif kind == SuffixKind.LOCATIVE:
        voice = "t" if _voiceless_ending(stem) else "d"
        ending = voice + _low_vowel(vowel)
    elif kind == SuffixKind.ABLATIVE:
        voice = "t" if _voiceless_ending(stem) else "d"
        ending = voice + _low_vowel(vowel) + "n"
    elif kind == SuffixKind.INSTRUMENTAL:
        ending = ("y" if use_y_glide else "") + ("le" if vowel in _FRONT else "la")
    elif kind == SuffixKind.RELATIVE:
        ending = "ki"
    elif kind == SuffixKind.LOCATIVE_RELATIVE:
        voice = "t" if _voiceless_ending(stem) else "d"
        ending = voice + _low_vowel(vowel) + "ki"
    else:
        ending = ("y" if use_y_glide else "") + _high_vowel(vowel)

    if apostrophe:
        return f"{stem}'{ending}"
    return f"{stem}{ending}"


def attach_turkish_suffix(
    stem: str,
    raw_suffix: str,
    *,
    apostrophe: bool = True,
    original_token: str | None = None,
) -> str:
    """Attach ``raw_suffix`` to ``stem`` with Turkish vowel harmony.

    Args:
        stem: Replacement surface (placeholder or role word).
        raw_suffix: Leftover after an apostrophe, e.g. ``ın`` or ``'in``.
        apostrophe: If True, keep the apostrophe (proper nouns / placeholders).
            If False, glue the ending onto a common noun (``Sanık`` → ``Sanığın``).
        original_token: Optional full original token for Zemberek classification
            of leftovers the local closed set does not cover.
    """
    suffix = raw_suffix.strip()
    if not suffix:
        return stem
    kind = classify_suffix(suffix, original_token=original_token)
    return inflect_case(
        stem,
        kind,
        apostrophe=apostrophe,
        original_suffix=suffix,
    )


def extract_trailing_apostrophe_suffix(right_context: str) -> re.Match[str] | None:
    """Match ``'ın`` / ``’e`` etc. at the start of the text after an entity span."""
    return _APOSTROPHE_SUFFIX_AT_START.match(right_context)
