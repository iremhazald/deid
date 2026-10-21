from __future__ import annotations

from app.detectors.textutil import fold_tr_identity
from app.domain.models import (
    EntityCandidate,
    EntityType,
    PrivacyProfile,
    TransformationStrategy,
)
from app.transforms.catalog import recommended_strategy


POLICY_VERSION = "2026.09-transforms.20"

# Resolved document language, not UI language. Matches locale_ids_for_document().
_ENGLISH_DOCUMENT_LOCALES = frozenset({"en", "en-us", "en-gb", "en-ca", "en-au", "english"})

NOTICE_RECIPIENT_ROLES = {"NOTICE_RECIPIENT"}
_NOTICE_RECIPIENT_LABELS = frozenset(
    {
        "ihtar olunan",
        "ihtar edilen",
        "muhatap",
    }
)


def apply_policy(
    candidates: list[EntityCandidate],
    profile: PrivacyProfile,
    locale: str | None = None,
) -> list[EntityCandidate]:
    """Recommend only; detection and user decisions remain independent.

    Category defaults come from ``recommended_strategy``. Attribute-level
    exceptions (notice recipient, docket header line, cited authority) stay
    overlayed on top. ``locale`` is the resolved document language
    (``job.locale``), never the UI language.
    """
    for candidate in candidates:
        if candidate.detector == "USER_DEFINED_TERM":
            candidate.recommended = True
            if (
                candidate.recommended_strategy is None
                or candidate.recommended_strategy == TransformationStrategy.KEEP
            ):
                candidate.recommended_strategy = TransformationStrategy.REDACT
            if not candidate.reason:
                candidate.reason = "User-defined term."
            continue

        strategy = recommended_strategy(
            candidate.type, role_confident=candidate.role_confident
        )
        recommended = strategy != TransformationStrategy.KEEP

        if profile == PrivacyProfile.CUSTOM:
            recommended = False

        if _is_notice_recipient(candidate) and candidate.type not in {
            EntityType.COMPANY_NAME,
            EntityType.ORGANISATION,
        }:
            recommended = True
            strategy = TransformationStrategy.REDACT
        elif candidate.type == EntityType.COURT_NAME:
            recommended, strategy = _court_name_policy(candidate, locale=locale)
        elif candidate.attributes.get("mask_scope") == "header_line":
            recommended = True
            strategy = TransformationStrategy.REDACT
        elif candidate.type in {EntityType.COMPANY_NAME, EntityType.ORGANISATION}:
            recommended = True
            strategy = TransformationStrategy.PLACEHOLDER

        if (candidate.attributes or {}).get("cited_authority_context"):
            # Span-local only. Same name elsewhere is not inferred public.
            recommended = False
            strategy = TransformationStrategy.KEEP

        candidate.recommended = recommended
        candidate.recommended_strategy = strategy
        if not candidate.reason:
            candidate.reason = (
                "Structured value passed deterministic validation."
                if candidate.validated
                else "Contextual candidate requires user review."
            )
    return candidates


def _is_english_document_locale(locale: str | None) -> bool:
    if not locale:
        return False
    return locale.strip().lower() in _ENGLISH_DOCUMENT_LOCALES


def _is_english_court(candidate: EntityCandidate, locale: str | None) -> bool:
    """English-General court surfaces use detector locale or resolved document language."""
    detector = candidate.detector or ""
    if detector.startswith("EN_"):
        return True
    if detector.startswith("TR_"):
        return False
    return _is_english_document_locale(locale)


def _court_name_policy(
    candidate: EntityCandidate, locale: str | None = None
) -> tuple[bool, TransformationStrategy]:
    """Turkish courts default to ordinal PLACEHOLDER; docket headers stay REDACT.

    ``Mersin 2. Tüketici Mahkemesi`` → ``Mersin X Tüketici Mahkemesi``.
    English-General ``EN_COURT`` names remain public KEEP labels. Locale is
    the resolved document language, not the UI language.
    """
    if candidate.attributes.get("mask_scope") == "header_line":
        return True, TransformationStrategy.REDACT
    if _is_english_court(candidate, locale):
        return False, TransformationStrategy.KEEP
    from app.detectors.legal.court import court_ordinal, is_duty_court

    if is_duty_court(candidate.text) and not court_ordinal(candidate.text):
        return False, TransformationStrategy.KEEP
    return True, TransformationStrategy.PLACEHOLDER


def _is_notice_recipient(candidate: EntityCandidate) -> bool:
    """İhtar olunan / muhatap — person or company — is permanently redacted by default."""
    role = (candidate.role or "").upper()
    if role in NOTICE_RECIPIENT_ROLES:
        return True
    label = str(candidate.attributes.get("legal_role") or "")
    return fold_tr_identity(label) in _NOTICE_RECIPIENT_LABELS
