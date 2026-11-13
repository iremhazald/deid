"""A rescan must not report the placeholder tokens the export just wrote."""

import asyncio

from app.detectors.locale_pack import locale_ids_for_document
from app.detectors.registry import PageText, run_detectors
from app.domain.models import ValidationStatus
from app.services.pipeline import _residual_checks

_TOKENS = (
    "Borçlu: [GİZLENDİ].",
    "Alacaklı: [REDACTED].",
    "Borçlu: [KİŞİ_1].",
)


def _pages(text: str) -> list[PageText]:
    return [PageText(page=0, text=text, document_offset=0)]


def _status(text: str) -> tuple[ValidationStatus, list[str]]:
    pages = _pages(text)
    found, _details = run_detectors(pages, locale_ids_for_document("tr"))
    assert found, text
    return asyncio.run(
        _residual_checks(
            output_text=text,
            output_pages=pages,
            selected_entities=found,
            kept_entities=[],
            resolved_document_language="tr",
        )
    )


def test_residual_check_ignores_redact_and_tag_tokens() -> None:
    for text in _TOKENS:
        status, messages = _status(text)
        assert status is ValidationStatus.PASS
        assert messages == []


def test_residual_check_still_reports_a_remaining_name() -> None:
    status, messages = _status("Borçlu: Cemre Dağ.")
    assert status is ValidationStatus.WARNING
    assert messages
