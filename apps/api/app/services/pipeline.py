from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pymupdf
from starlette.concurrency import run_in_threadpool

from app.detectors.legal.court import court_ordinal, detect_court_letterheads, page_line_rects
from app.detectors.legal.repeats import DETECTOR_NAME as NAME_REPEAT_DETECTOR
from app.detectors.legal.repeats import PAIR_DETECTOR_NAME
from app.detectors.legal.repeats import pair_adjacent_person_name_tokens
from app.detectors.legal.repeats import propagate_person_name_repeats, variant_pattern
from app.detectors.legal.identifier_repeats import (
    IBAN_REPEAT,
    PHONE_REPEAT,
    PORT_REPEAT,
    propagate_identifier_repeats,
)
from app.detectors.qrcodes import DETECTOR_NAME as QR_DETECTOR_NAME
from app.detectors.qrcodes import detect_qrcodes
from app.detectors.custom_terms import detect_user_terms, drop_hits_inside_person_spans
from app.detectors.locale_pack import locale_ids_for_document
from app.language.resolve import resolve_document_language
from app.detectors.registry import PageText, run_detectors
from app.detectors.structural import run_structural_detectors
from app.detectors.textutil import fold_tr_identity
from app.detectors.verification import apply_verification
from app.domain.models import (
    AIRunStatus,
    AnalysisResponse,
    AnalysisStatus,
    AuditReport,
    DetectionMethod,
    DetectionMode,
    DocumentKind,
    EntityCandidate,
    EntityType,
    LocalNERStatus,
    PreviewOperation,
    PreviewResponse,
    PrivacyProfile,
    RedactionRequest,
    TransformationStrategy,
    ValidationResult,
    ValidationStatus,
)
from app.policy.engine import POLICY_VERSION, apply_policy
from app.services.document_processing import (
    extract_docx,
    extract_generated_output,
    extract_pdf_with_ocr,
    write_text_output,
)
from app.services.jobs import Job, SpanBox
from app.transforms.planner import (
    apply_operations,
    build_operations,
    requires_text_rebuild,
)
from app.transforms.entity_merge import placeholder_tokens_for_operations
from app.transforms.possible_matches import generate_possible_matches
from app.transforms.tag_registry import (
    bind_canonical_ids,
    stamp_placeholder_tokens,
    tag_locale_for_job,
)
from app.transforms.strategies import COURT_ORDINAL_TAG, TransformOp
from app.transforms.catalog import filter_by_scan_types
from app.transforms.resolution import assign_resolved_entities
from app.transforms.validate import (
    build_transformation_audit,
    merge_residual_messages,
    soften_pdf_text_residuals,
    validate_operations,
)

_METHOD_PRIORITY = {
    DetectionMethod.DETERMINISTIC: 0,
    DetectionMethod.STRUCTURAL: 1,
    DetectionMethod.AI: 2,
    DetectionMethod.MANUAL: 3,
}

APP_VERSION = "0.2.2"
REDACT_IMAGE_PIXELS = 2


class DocumentError(ValueError):
    pass


logger = logging.getLogger(__name__)


def _open_pdf(path: Path) -> pymupdf.Document:
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise DocumentError("PDF_CORRUPT") from exc
    if document.needs_pass:
        document.close()
        raise DocumentError("PDF_ENCRYPTED")
    return document


def _extract_pages(document: pymupdf.Document) -> tuple[list[PageText], str]:
    pages: list[PageText] = []
    chunks: list[str] = []
    offset = 0
    for page_number in range(document.page_count):
        page = document[page_number]
        text = str(page.get_text("text"))
        pages.append(PageText(page_number, text, offset))
        chunks.append(text)
        offset += len(text)
    return pages, "".join(chunks)


def _extract_pdf_source(
    path: Path,
) -> tuple[list[PageText], str, list[SpanBox], bool, int]:
    """Open, extract and close a source PDF inside a single thread.

    PyMuPDF documents must not be handed across await points, so the whole
    open/extract/close cycle stays in one worker thread.
    """
    document = _open_pdf(path)
    try:
        try:
            pages, text, span_boxes, ocr_used = extract_pdf_with_ocr(document)
        except Exception as exc:
            raise DocumentError("OCR_FAILED") from exc
        return pages, text, span_boxes, ocr_used, document.page_count
    finally:
        document.close()


def _read_source_text(job: Job) -> str:
    return (
        extract_docx(job.source_path)
        if job.document_kind == DocumentKind.DOCX
        else job.source_path.read_text(encoding="utf-8")
    )


def _hash_source(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def analyze_pdf(
    job: Job,
    profile: PrivacyProfile,
    ai_provider: object | None = None,
    mode: DetectionMode = DetectionMode.LOCAL_CONTEXT,
) -> AnalysisResponse:
    del ai_provider
    pages, text, span_boxes, ocr_used, page_count = await run_in_threadpool(
        _extract_pdf_source, job.source_path
    )
    warnings = ["OCR_USED"] if ocr_used else []
    if not text.strip():
        visual = await run_in_threadpool(detect_qrcodes, job.source_path, "")
        if not visual:
            raise DocumentError("OCR_FAILED")
        text = " "
        warnings.append("VISUAL_ONLY_DOCUMENT")
    job.span_boxes = span_boxes
    return await _build_analysis(
        job, pages, text, page_count, profile, warnings, mode
    )


async def analyze_textual_document(
    job: Job,
    profile: PrivacyProfile,
    ai_provider: object | None = None,
    mode: DetectionMode = DetectionMode.LOCAL_CONTEXT,
) -> AnalysisResponse:
    del ai_provider
    try:
        text = await run_in_threadpool(_read_source_text, job)
    except (OSError, UnicodeError, ValueError) as exc:
        code = str(exc) if str(exc).isupper() else "DOCUMENT_READ_FAILED"
        raise DocumentError(code) from exc
    if not text.strip():
        raise DocumentError("EMPTY_DOCUMENT")
    warnings = (
        ["DOCX_REBUILT_TEXT_ONLY"]
        if job.document_kind == DocumentKind.DOCX
        else []
    )
    pages = [PageText(page=0, text=text, document_offset=0)]
    return await _build_analysis(
        job, pages, text, 1, profile, warnings, mode
    )


def _consolidate_candidates(
    candidates: list[EntityCandidate],
    profile: PrivacyProfile,
    locale: str | None = None,
    pages: list[PageText] | None = None,
) -> tuple[int, list[EntityCandidate], list[EntityCandidate]]:
    """Deduplicate, resolve and score candidates. Runs in a worker thread.

    Scales with entity count rather than document size, and a form-heavy
    document can produce thousands, so this stays off the event loop too.
    """
    deduplicated: dict[tuple[int, int, str], EntityCandidate] = {}
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item.start,
            _METHOD_PRIORITY.get(item.method, 99),
        ),
    ):
        deduplicated.setdefault((candidate.start, candidate.end, candidate.type), candidate)
    from app.detectors.en.citations import annotate_cited_authority_context
    from app.detectors.legal.merge import merge_rule_candidates

    unique = merge_rule_candidates(list(deduplicated.values()))
    unique = _drop_contained_in_uyap_footer(unique)
    if pages:
        unique = annotate_cited_authority_context(pages, unique)
    resolved = assign_resolved_entities(unique)
    return len(unique), resolved, apply_policy(resolved, profile, locale=locale)


def _drop_contained_in_uyap_footer(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    covers = [item for item in candidates if item.type == EntityType.UYAP_ACCESS]
    if not covers:
        return candidates
    kept: list[EntityCandidate] = []
    for candidate in candidates:
        if candidate.type == EntityType.UYAP_ACCESS:
            kept.append(candidate)
            continue
        contained = any(
            cover.page == candidate.page
            and candidate.start >= cover.start
            and candidate.end <= cover.end
            for cover in covers
        )
        if not contained:
            kept.append(candidate)
    return kept


async def _build_analysis(
    job: Job,
    pages: list[PageText],
    text: str,
    page_count: int,
    profile: PrivacyProfile,
    warnings: list[str],
    mode: DetectionMode = DetectionMode.LOCAL_CONTEXT,
) -> AnalysisResponse:
    requested = getattr(job, "requested_document_language", None)
    if requested is None:
        requested = getattr(job, "locale", None)
    resolved_language = resolve_document_language(requested, pages)
    job.locale = resolved_language
    logger.info(
        "[scan] job=%s mode=%s language=%s local_ner_requested=%s",
        job.id,
        mode.value,
        resolved_language,
        "YES" if mode == DetectionMode.LOCAL_CONTEXT else "NO",
    )
    locale_ids = locale_ids_for_document(resolved_language)
    deterministic, detectors = await run_in_threadpool(run_detectors, pages, locale_ids)
    structural = await run_in_threadpool(run_structural_detectors, pages)
    detectors.append("STRUCTURAL_LABEL_VALUE")
    candidates = list(deterministic) + list(structural)
    if job.custom_terms:
        custom = await run_in_threadpool(detect_user_terms, pages, job.custom_terms)
        if custom:
            candidates.extend(custom)
            detectors.append("USER_DEFINED_TERM")
    candidates = apply_verification(candidates)
    candidates = filter_by_scan_types(candidates, job.scan_types)
    if job.document_kind == DocumentKind.PDF:
        letterheads = await run_in_threadpool(detect_court_letterheads, job.source_path, text)
        if letterheads:
            candidates.extend(letterheads)
            detectors.append("TR_COURT_LETTERHEAD")
        qr_entities = await run_in_threadpool(detect_qrcodes, job.source_path, text)
        if qr_entities:
            candidates.extend(qr_entities)
            detectors.append(QR_DETECTOR_NAME)
    routing = None
    ai_status = AIRunStatus.SKIPPED
    analysis_status = AnalysisStatus.COMPLETE
    ai_error_code = None
    ai_error_message = None
    local_ner_status = LocalNERStatus.NOT_REQUESTED
    local_ner_language = None
    local_ner_provider = None
    local_ner_candidate_count = None
    local_ner_error_code = None
    local_ner_error_message = None

    if mode == DetectionMode.RULES_ONLY:
        if not candidates:
            analysis_status = AnalysisStatus.COMPLETE
    else:
        # LOCAL_CONTEXT: NER runs only after deterministic + structural +
        # custom + PDF extras. Candidates then enter existing evidence scoring
        # and merge/repeats below. RULES_ONLY never reaches this branch.
        from app.ner.runtime import run_local_ner_layer

        locale = getattr(job, "locale", None)
        ner_run = await run_in_threadpool(run_local_ner_layer, pages, candidates, locale)
        local_ner_status = ner_run.status
        local_ner_language = ner_run.language
        local_ner_provider = ner_run.provider
        local_ner_candidate_count = ner_run.candidate_count
        local_ner_error_code = ner_run.error_code
        local_ner_error_message = ner_run.error_message
        if ner_run.error_code:
            warnings.append(ner_run.error_code)
        if ner_run.candidates:
            candidates.extend(ner_run.candidates)
            candidates = apply_verification(candidates)
        for name in ner_run.detectors:
            if name not in detectors:
                detectors.append(name)
        if ner_run.status in {LocalNERStatus.UNAVAILABLE, LocalNERStatus.FAILED}:
            analysis_status = (
                AnalysisStatus.PARTIAL if candidates else AnalysisStatus.FAILED
            )

    from app.detectors.legal.merge import merge_rule_candidates

    candidates = merge_rule_candidates(candidates)
    paired = await run_in_threadpool(pair_adjacent_person_name_tokens, pages, candidates)
    if paired:
        candidates = merge_rule_candidates(candidates + paired)
        if PAIR_DETECTOR_NAME not in detectors:
            detectors.append(PAIR_DETECTOR_NAME)
    repeats = await run_in_threadpool(propagate_person_name_repeats, pages, candidates)
    if repeats:
        candidates.extend(repeats)
        if NAME_REPEAT_DETECTOR not in detectors:
            detectors.append(NAME_REPEAT_DETECTOR)
    identifiers = await run_in_threadpool(propagate_identifier_repeats, pages, candidates)
    if identifiers:
        candidates.extend(identifiers)
        for detector in (IBAN_REPEAT, PHONE_REPEAT, PORT_REPEAT):
            if detector not in detectors and any(item.detector == detector for item in identifiers):
                detectors.append(detector)

    after_dedup, resolved, entities = await run_in_threadpool(
        _consolidate_candidates, candidates, profile, job.locale, pages
    )
    del after_dedup, resolved
    if job.custom_terms:
        entities = _apply_term_strategies(entities, job.custom_terms)
    entities = stamp_placeholder_tokens(
        entities, resolved_language, state=job.resolution_state
    )
    possible_matches = generate_possible_matches(
        entities, text, job.resolution_state
    )

    document_hash = await run_in_threadpool(_hash_source, job.source_path)
    page_texts_list = [page.text for page in pages]
    analysis = AnalysisResponse(
        job_id=job.id,
        file_name=job.source_path.name,
        document_kind=job.document_kind,
        document_hash=document_hash,
        page_count=page_count,
        text=text,
        page_texts=page_texts_list,
        entities=entities,
        detectors_executed=detectors,
        warnings=warnings,
        profile=profile,
        detection_mode=mode,
        routing=routing,
        analysis_status=analysis_status,
        ai_status=ai_status,
        ai_error_code=ai_error_code,
        ai_error_message=ai_error_message,
        local_ner_status=local_ner_status,
        local_ner_language=local_ner_language,
        local_ner_provider=local_ner_provider,
        local_ner_candidate_count=local_ner_candidate_count,
        local_ner_error_code=local_ner_error_code,
        local_ner_error_message=local_ner_error_message,
        requested_document_language=getattr(job, "requested_document_language", None),
        resolved_document_language=resolved_language,
        possible_matches=possible_matches,
        resolution_state=job.resolution_state,
    )
    job.analysis = analysis
    job.page_texts = page_texts_list
    if job.document_kind == DocumentKind.PDF:
        try:
            page_spans = collect_page_spans(job)
        except (ValueError, TypeError, RuntimeError, OSError):
            page_spans = []
            warnings.append("SPAN_MAPPING_FAILED")
        analysis.page_spans = page_spans
        analysis.warnings = warnings
        job.page_spans = page_spans
    return analysis


def _page_preview_payload(job: Job) -> list[dict]:
    previews: list[dict] = []
    prefix = f":{PAGE_PREVIEW_SCALE:g}"
    for key, raw in job.page_images.items():
        if not key.endswith(prefix) or not raw:
            continue
        page_num = key[: -len(prefix)]
        if not page_num.isdigit():
            continue
        previews.append(
            {
                "page": int(page_num),
                "image": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
            }
        )
    previews.sort(key=lambda item: item["page"])
    return previews


def _apply_term_strategies(entities: list[EntityCandidate], terms: list) -> list[EntityCandidate]:
    by_value = {
        fold_tr_identity(getattr(term, "value", "") or ""): term
        for term in terms
        if getattr(term, "strategy", None)
    }
    if not by_value:
        return entities
    updated: list[EntityCandidate] = []
    for entity in entities:
        if entity.detector != "USER_DEFINED_TERM":
            updated.append(entity)
            continue
        term = by_value.get(fold_tr_identity(entity.text))
        if term is None:
            raw = (entity.attributes or {}).get("term")
            term = by_value.get(fold_tr_identity(str(raw))) if raw else None
        if term and term.strategy:
            updated.append(
                entity.model_copy(
                    update={
                        "recommended_strategy": term.strategy,
                        "recommended": term.strategy != TransformationStrategy.KEEP,
                    }
                )
            )
        else:
            updated.append(entity)
    return updated


def add_custom_terms_to_analysis(job: Job, terms: list) -> AnalysisResponse:
    if not job.analysis:
        raise DocumentError("ANALYSIS_REQUIRED")
    job.custom_terms = list(job.custom_terms) + list(terms)
    pages = _pages_from_job(job, job.analysis.text)
    fresh = apply_verification(detect_user_terms(pages, terms))
    fresh = drop_hits_inside_person_spans(fresh, job.analysis.entities)
    existing = {(item.start, item.end, item.type) for item in job.analysis.entities}
    merged = list(job.analysis.entities)
    for item in fresh:
        if (item.start, item.end, item.type) not in existing:
            merged.append(item)
    _, resolved, scored = _consolidate_candidates(
        merged, job.analysis.profile, job.locale, pages
    )
    scored = _apply_term_strategies(scored, job.custom_terms)
    scored = bind_canonical_ids(scored, job.resolution_state)
    scored = stamp_placeholder_tokens(
        scored,
        tag_locale_for_job(job),
        state=job.resolution_state,
        append_new=True,
    )
    matches = generate_possible_matches(
        scored, job.analysis.text, job.resolution_state
    )
    job.analysis = job.analysis.model_copy(
        update={
            "entities": scored,
            "possible_matches": matches,
            "resolution_state": job.resolution_state,
        }
    )
    if job.document_kind == DocumentKind.PDF:
        try:
            job.analysis = job.analysis.model_copy(update={"page_spans": collect_page_spans(job)})
        except (ValueError, TypeError, RuntimeError, OSError):
            pass
    return job.analysis


def _pages_from_job(job: Job, text: str) -> list[PageText]:
    page_texts = job.page_texts or [text]
    pages: list[PageText] = []
    offset = 0
    for index, page_text in enumerate(page_texts):
        pages.append(PageText(page=index, text=page_text, document_offset=offset))
        offset += len(page_text)
    if offset == 0 and text:
        return [PageText(page=0, text=text, document_offset=0)]
    return pages


def _rects_for_occurrence(
    rectangles: list[pymupdf.Rect], occurrence_count: int, rank: int
) -> list[pymupdf.Rect]:
    """Keep every word box that belongs to one mention.

    PyMuPDF often returns one rectangle per word for a multi-word name. Taking
    only ``rectangles[rank]`` would redact ``İPEK`` and leave ``OKYAY`` visible.
    """
    if not rectangles or occurrence_count <= 0 or rank < 0 or rank >= occurrence_count:
        return []
    count = len(rectangles)
    if count == occurrence_count:
        return [rectangles[rank]]
    if count % occurrence_count == 0:
        size = count // occurrence_count
        return list(rectangles[rank * size : (rank + 1) * size])
    if occurrence_count == 1:
        return list(rectangles)
    return [rectangles[min(rank, count - 1)]]


def _phone_logical_key(text: str) -> str:
    """National 10-digit mobile key shared by 0531 / 0 531 / 531 groupings."""
    digits = _digit_key(text)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("90") and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


def _identifier_logical_key(text: str) -> tuple[str, str]:
    if _looks_like_iban_needle(text):
        return "iban", _iban_map_key(text)
    if _looks_like_phone_needle(text):
        return "phone", _phone_logical_key(text)
    return "", ""


def _logical_identifier_starts(page_text: str, text: str) -> list[int]:
    """Starts of every same-logical IBAN/phone, ignoring whitespace grouping.

    Exact-string find() under-counts when two detections of one identifier
    use different spacing (newline wrap vs official groups vs irregular
    groups). PDF word-groups still list both, so occurrence pick must use
    this normalized rank — otherwise every variant maps to group 0.
    """
    kind, needle = _identifier_logical_key(text)
    if not needle:
        return []
    starts: list[int] = []
    index = 0
    length = len(page_text)
    while index < length:
        acc = ""
        start = None
        cursor = index
        matched = False
        while cursor < length:
            char = page_text[cursor]
            piece = _iban_map_key(char) if kind == "iban" else _digit_key(char)
            if piece:
                if start is None:
                    start = cursor
                trial = acc + piece
                if kind == "phone":
                    acc = trial
                    if _phone_logical_key(acc) == needle:
                        nxt = cursor + 1
                        while nxt < length and (
                            page_text[nxt].isspace() or page_text[nxt] in "-()."
                        ):
                            nxt += 1
                        if nxt >= length or not page_text[nxt].isdigit():
                            starts.append(start)
                            index = cursor + 1
                            matched = True
                            break
                    if len(acc) > 14:
                        break
                else:
                    if needle.startswith(trial) or trial.startswith(needle):
                        acc = trial
                    else:
                        break
                    extra = acc[len(needle) :] if acc.startswith(needle) else ""
                    if acc == needle or (extra and _iban_label_extra(extra)):
                        starts.append(start)
                        index = cursor + 1
                        matched = True
                        break
                    if len(acc) > len(needle):
                        break
            elif acc:
                if char.isspace() or char in "'’:-./;":
                    cursor += 1
                    continue
                break
            cursor += 1
        if not matched:
            index += 1
    return starts


def _rect_for_needle(
    page: pymupdf.Page, page_text: str, text: str, relative_start: int
) -> list[pymupdf.Rect]:
    exact_positions = _occurrence_starts(page_text, text)
    logical_positions = _logical_identifier_starts(page_text, text)
    positions = logical_positions or exact_positions
    groups: list = []
    if _looks_like_phone_needle(text):
        groups = _digit_run_word_groups(page, text)
    elif _looks_like_iban_needle(text):
        groups = _run_iban_word_groups(page, text)
    elif _looks_like_name_needle(text):
        groups = _run_word_groups(page, text, _search_token_key, 6)
    if not groups:
        groups = _token_run_word_groups(page, text)
    if not groups:
        groups = _single_token_word_groups(page, text)
    if groups:
        index = _pick_occurrence_index(positions, relative_start, len(groups))
        return _union_rects_by_line(groups[index])
    tokens = _normalize_search_text(text).split()
    if (
        len(tokens) == 1
        and any(char.isalpha() for char in tokens[0])
        and _pdf_words(page)
    ):
        rectangles = _search_rects(page, text)
    else:
        rectangles = list(page.search_for(text) or [])
        if not rectangles:
            rectangles = _search_rects(page, text)
    if not rectangles:
        return []
    if relative_start in positions:
        index = positions.index(relative_start)
    elif positions:
        index = min(range(len(positions)), key=lambda item: abs(positions[item] - relative_start))
    else:
        return rectangles[:1]
    return _rects_for_occurrence(rectangles, max(len(positions), 1), index)


def _rect_for_entity(
    page: pymupdf.Page,
    page_text: str,
    text: str,
    relative_start: int,
    relative_end: int | None = None,
) -> list[pymupdf.Rect]:
    needles: list[str] = []
    if (
        relative_end is not None
        and 0 <= relative_start < relative_end <= len(page_text)
    ):
        surface = page_text[relative_start:relative_end].strip()
        if surface:
            needles.append(surface)
    if text and text not in needles:
        needles.append(text)
    for needle in needles:
        found = _rect_for_needle(page, page_text, needle, relative_start)
        if found:
            return found
    return []


def _occurrence_starts(page_text: str, text: str) -> list[int]:
    positions: list[int] = []
    cursor = 0
    while True:
        found = page_text.find(text, cursor)
        if found < 0:
            break
        positions.append(found)
        cursor = found + max(1, len(text))
    pattern = variant_pattern(text)
    if pattern is not None:
        for match in pattern.finditer(page_text):
            if match.start() not in positions:
                positions.append(match.start())
        positions.sort()
    from app.detectors.custom_terms import _term_pattern

    folded_pattern = _term_pattern(text)
    if folded_pattern is not None:
        for match in folded_pattern.finditer(page_text):
            if match.start() not in positions:
                positions.append(match.start())
        positions.sort()
    return positions


def _ocr_mapping_coarse(job: Job, entity: EntityCandidate) -> bool:
    matching = [
        span
        for span in job.span_boxes
        if span.page == entity.page
        and entity.start < span.end
        and entity.end > span.start
    ]
    if not matching:
        return False
    return any(span.start < entity.start or span.end > entity.end for span in matching)


def _normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _page_index(page: pymupdf.Page) -> int:
    number = page.number
    return int(number) if number is not None else 0


def _pdf_words(page: pymupdf.Page) -> list[Sequence[Any]]:
    raw: Any = page.get_text("words")
    return raw if isinstance(raw, list) else []


def _uyap_access_rects(page: pymupdf.Page, entity_text: str) -> list[pymupdf.Rect]:
    """Cover the footer from the UYAP URL through the closing access phrase."""
    words = _pdf_words(page)
    if not words:
        return _search_rects(page, entity_text)
    url_index = next(
        (
            index
            for index, word in enumerate(words)
            if "vatandas.uyap.gov.tr" in str(word[4]).lower()
            or "vatandas" in str(word[4]).lower()
        ),
        None,
    )
    if url_index is None:
        return _search_rects(page, entity_text)

    url = words[url_index]
    y_mid = (float(url[1]) + float(url[3])) / 2
    line_tol = max(8.0, (float(url[3]) - float(url[1])) * 1.1)
    start_index = url_index
    while start_index > 0:
        previous = words[start_index - 1]
        prev_mid = (float(previous[1]) + float(previous[3])) / 2
        if abs(prev_mid - y_mid) > line_tol:
            break
        start_index -= 1

    selected = words[start_index : url_index + 1]
    for index in range(url_index + 1, len(words)):
        word = words[index]
        token = str(word[4])
        nxt = str(words[index + 1][4]) if index + 1 < len(words) else ""
        selected.append(word)
        if token.lower() == "ile" and nxt.lower().startswith("erişebilirsin"):
            selected.append(words[index + 1])
            period = words[index + 2] if index + 2 < len(words) else None
            if period is not None and str(period[4]) in {".", "..."}:
                selected.append(period)
            break
        word_mid = (float(word[1]) + float(word[3])) / 2
        if word_mid > y_mid + line_tol * 3.5:
            break

    if not selected:
        return _search_rects(page, entity_text)
    return _union_rects_by_line(selected)


def _union_rects_by_line(words: Sequence[Sequence[Any]]) -> list[pymupdf.Rect]:
    groups: list[list[Sequence[Any]]] = []
    for word in words:
        mid = (float(word[1]) + float(word[3])) / 2
        placed = False
        for group in groups:
            gmid = (float(group[0][1]) + float(group[0][3])) / 2
            if abs(mid - gmid) <= max(6.0, (float(word[3]) - float(word[1])) * 0.9):
                group.append(word)
                placed = True
                break
        if not placed:
            groups.append([word])
    rectangles: list[pymupdf.Rect] = []
    for group in groups:
        x0 = min(float(item[0]) for item in group)
        y0 = min(float(item[1]) for item in group)
        x1 = max(float(item[2]) for item in group)
        y1 = max(float(item[3]) for item in group)
        rectangles.append(pymupdf.Rect(x0, y0, x1, y1))
    return rectangles


def _rects_near(left: pymupdf.Rect, right: pymupdf.Rect, pad: float = 24.0) -> bool:
    expanded = pymupdf.Rect(right.x0 - pad, right.y0 - pad, right.x1 + pad, right.y1 + pad)
    return left.intersects(expanded)


def _ordinal_rects_left_of(page: pymupdf.Page, court_rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Pick a 9. sitting on the same line, just left of the court type."""
    if not court_rects:
        return []
    words = _pdf_words(page)
    found: list[pymupdf.Rect] = []
    for cover in court_rects:
        for index, word in enumerate(words):
            token = str(word[4]).strip()
            box = pymupdf.Rect(word[0], word[1], word[2], word[3])
            if token.isdigit() and index + 1 < len(words) and str(words[index + 1][4]).strip() == ".":
                nxt = words[index + 1]
                box = box | pymupdf.Rect(nxt[0], nxt[1], nxt[2], nxt[3])
                token = f"{token}."
            if not re.fullmatch(r"\d{1,3}\.", token):
                continue
            mid = (box.y0 + box.y1) / 2
            cover_mid = (cover.y0 + cover.y1) / 2
            same_line = abs(mid - cover_mid) <= max(10.0, cover.height)
            if not same_line:
                continue
            inside = cover.intersects(box) or cover.contains(box)
            just_left = box.x1 <= cover.x0 + 8 and cover.x0 - box.x1 <= 80
            just_right = box.x0 >= cover.x1 - 8 and box.x0 - cover.x1 <= 80
            if inside or just_left or just_right:
                found.append(box)
    return found


def _court_ordinal_rects(
    page: pymupdf.Page,
    entity_text: str,
    court_rects: list[pymupdf.Rect],
    attributes: dict | None = None,
) -> list[pymupdf.Rect]:
    """Locate only the chamber number so the city and court type stay visible."""
    stored = (attributes or {}).get("ordinal_rect")
    hits: list[pymupdf.Rect] = []
    if isinstance(stored, dict) and {"x0", "y0", "x1", "y1"} <= stored.keys():
        hits = [pymupdf.Rect(stored["x0"], stored["y0"], stored["x1"], stored["y1"])]
    else:
        token = court_ordinal(entity_text)
        if token:
            for needle in {token, token.replace(".", " .")}:
                for rect in list(page.search_for(needle) or []):
                    if not court_rects or any(_rects_near(rect, cover) for cover in court_rects):
                        hits.append(rect)
        if not hits:
            hits = _ordinal_rects_left_of(page, court_rects)
    pad = 1.4
    clip = page.rect
    return [
        pymupdf.Rect(
            max(clip.x0, rect.x0 - pad),
            max(clip.y0, rect.y0 - 0.6),
            min(clip.x1, rect.x1 + pad),
            min(clip.y1, rect.y1 + 0.6),
        )
        for rect in hits
    ]


_CASE_SUFFIX = re.compile(
    r"['’`´ʼ′](?:in|ın|un|ün|nin|nın|nun|nün|ye|ya|den|dan|ten|tan|"
    r"dir|dır|dur|dür|tir|tır|tur|tür|de|da|te|ta|e|a|i|ı|u|ü)$",
    re.IGNORECASE,
)
_IBAN_WORD_TAIL = {
    "iban",
    "ibana",
    "no",
    "n",
    "numara",
    "numarasi",
    "numarası",
    "dir",
    "dır",
    "dur",
    "dür",
    "tir",
    "tır",
    "tur",
    "tür",
}


def _alnum_key(value: str) -> str:
    compact = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü]", "", value)
    return fold_tr_identity(compact)


def _iban_map_key(value: str) -> str:
    """Letters+digits of an IBAN word, without 'dir / İbana glued to the tail."""
    stripped = _CASE_SUFFIX.sub("", value.strip())
    key = _alnum_key(stripped)
    extras = sorted(_IBAN_WORD_TAIL, key=len, reverse=True)
    for extra in extras:
        folded = fold_tr_identity(extra)
        if key.endswith(folded) and len(key) - len(folded) >= 12:
            return key[: -len(folded)]
    return key


def _iban_start_piece(key: str, needle: str) -> str:
    """Allow 'yazıda;TR97…' to start matching at the trailing TR."""
    if not key:
        return ""
    if needle.startswith(key):
        return key
    if key.startswith(needle) and _iban_label_extra(key[len(needle) :]):
        return key
    found = ""
    pos = 0
    while True:
        index = key.find("tr", pos)
        if index < 0:
            break
        suffix = key[index:]
        if needle.startswith(suffix) or (
            suffix.startswith(needle) and _iban_label_extra(suffix[len(needle) :])
        ):
            found = suffix
        pos = index + 1
    return found


def _iban_start_key(label: str, needle: str) -> str:
    return _iban_start_piece(_iban_map_key(label), needle)


def _run_iban_word_groups(page: pymupdf.Page, text: str) -> list[list[Sequence[Any]]]:
    groups = _run_word_groups(
        page, text, _iban_map_key, 12, start_key_fn=_iban_start_key
    )
    if groups:
        return groups
    digits = _digit_key(text)
    if len(digits) < 24:
        return []
    return _run_word_groups(page, digits[-24:], _digit_key, 20)


def _search_token_key(value: str) -> str:
    stripped = _CASE_SUFFIX.sub("", value.strip())
    return _alnum_key(stripped)


def _same_search_token(left: str, right: str) -> bool:
    left_key = _search_token_key(left)
    right_key = _search_token_key(right)
    if not right_key:
        return False
    if left_key == right_key:
        return True
    if left_key.endswith(right_key):
        prefix = left_key[: -len(right_key)]
        return bool(prefix) and prefix.isdigit()
    return False


def _first_token_piece(piece: str, needle: str) -> str:
    """Map a glued PDF word such as ``5-Keşif`` onto the start of ``keşif harcı``."""
    if not piece:
        return ""
    if needle.startswith(piece):
        return piece
    trimmed = piece.lstrip("0123456789")
    if trimmed and trimmed != piece and needle.startswith(trimmed):
        return trimmed
    return ""


def _iban_label_extra(extra: str) -> bool:
    if not extra:
        return False
    folded = fold_tr_identity(extra)
    return folded in _IBAN_WORD_TAIL or folded.startswith("iban") or folded.startswith("numara")


def _digit_key(value: str) -> str:
    return re.sub(r"\D", "", value)


def _looks_like_phone_needle(text: str) -> bool:
    digits = _digit_key(text)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("90") and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return len(digits) == 10 and digits.startswith("5")


def _looks_like_iban_needle(text: str) -> bool:
    compact = re.sub(r"[\s-]", "", text)
    if not 15 <= len(compact) <= 34:
        return False
    return compact[:2].isalpha() and compact[2:4].isdigit()


def _looks_like_name_needle(text: str) -> bool:
    key = _search_token_key(text)
    if len(key) < 6 or any(char.isdigit() for char in key):
        return False
    tokens = [token for token in _normalize_search_text(text).split() if _search_token_key(token)]
    return len(tokens) >= 2 or len(key) >= 8


def _pick_occurrence_index(
    positions: list[int], relative_start: int, count: int
) -> int:
    if count <= 0:
        return 0
    if relative_start in positions:
        index = positions.index(relative_start)
    elif positions:
        index = min(range(len(positions)), key=lambda item: abs(positions[item] - relative_start))
    else:
        index = 0
    return min(max(index, 0), count - 1)


def _run_word_groups(
    page: pymupdf.Page, text: str, key_fn, min_len: int, *, start_key_fn=None
) -> list[list[Sequence[Any]]]:
    needle = key_fn(text)
    if len(needle) < min_len:
        return []
    words = _pdf_words(page)
    if not words:
        return []
    matches: list[list[Sequence[Any]]] = []
    index = 0
    while index < len(words):
        acc = ""
        start = None
        consumed_until = index
        for end in range(index, len(words)):
            label = str(words[end][4])
            piece = (
                start_key_fn(label, needle)
                if start_key_fn is not None and not acc
                else key_fn(label)
            )
            if not piece:
                if acc and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", label):
                    break
                continue
            if start is None:
                if start_key_fn is None:
                    piece = _first_token_piece(piece, needle)
                    if not piece:
                        continue
                start = end
            acc += piece
            consumed_until = end
            if acc == needle or (
                acc.startswith(needle) and _iban_label_extra(acc[len(needle) :])
            ):
                matches.append(words[start : end + 1])
                acc = needle
                break
            if len(acc) > len(needle) or not needle.startswith(acc):
                break
        index = max(index + 1, consumed_until + 1) if acc == needle else index + 1
    return matches


def _digit_run_word_groups(page: pymupdf.Page, text: str) -> list[list[Sequence[Any]]]:
    """Consecutive PDF words whose digits reconstruct a phone / identifier."""
    return _run_word_groups(page, text, _digit_key, 10)


def _alnum_run_word_groups(page: pymupdf.Page, text: str) -> list[list[Sequence[Any]]]:
    return _run_word_groups(page, text, _alnum_key, 12)


def _single_token_word_groups(page: pymupdf.Page, text: str) -> list[list[Sequence[Any]]]:
    """Exact whole-token hits for a 1-word needle.

    ``page.search_for("Page")`` is a case-insensitive prefix search, so it
    also hits ordinary ``pages``. Person occurrence mapping must not.
    """
    tokens = _normalize_search_text(text).split()
    if len(tokens) != 1:
        return []
    needle = tokens[0]
    if not any(char.isalpha() for char in needle):
        return []
    words = _pdf_words(page)
    if not words:
        return []
    return [
        [word]
        for word in words
        if _same_search_token(str(word[4]), needle)
    ]


def _token_run_word_groups(page: pymupdf.Page, text: str) -> list[list[Sequence[Any]]]:
    tokens = _normalize_search_text(text).split()
    if len(tokens) < 2:
        return []
    words = _pdf_words(page)
    if not words:
        return []
    labels = [str(word[4]) for word in words]
    matches: list[list[Sequence[Any]]] = []
    count = len(tokens)
    index = 0
    while index <= len(words) - count:
        window = labels[index : index + count]
        if all(_same_search_token(window[offset], tokens[offset]) for offset in range(count)):
            matches.append(words[index : index + count])
            index += count
            continue
        index += 1
    return matches


def _search_rects_by_digits(page: pymupdf.Page, text: str) -> list[pymupdf.Rect]:
    found: list[pymupdf.Rect] = []
    for group in _digit_run_word_groups(page, text):
        found.extend(_union_rects_by_line(group))
    return found


def _search_rects_by_words(page: pymupdf.Page, text: str) -> list[pymupdf.Rect]:
    """Map a span onto consecutive PDF words when search_for misses spacing or case."""
    needle = _normalize_search_text(text)
    tokens = needle.split()
    words = _pdf_words(page)
    if not words:
        return []
    labels = [str(word[4]) for word in words]
    if tokens:
        count = len(tokens)
        for index in range(len(words) - count + 1):
            window = labels[index : index + count]
            if all(_same_search_token(window[offset], tokens[offset]) for offset in range(count)):
                return _union_rects_by_line(words[index : index + count])
    key_fn = _iban_map_key if _looks_like_iban_needle(text) else _alnum_key
    compact = key_fn(needle)
    if len(compact) < 5:
        return []
    for start in range(len(words)):
        acc = ""
        for end in range(start, len(words)):
            piece = (
                _iban_start_key(labels[end], compact)
                if key_fn is _iban_map_key and not acc
                else key_fn(labels[end])
            )
            if not piece:
                if acc:
                    break
                continue
            acc += piece
            if acc == compact or (
                acc.startswith(compact) and _iban_label_extra(acc[len(compact) :])
            ):
                return _union_rects_by_line(words[start : end + 1])
            if not compact.startswith(acc):
                break
    return []


def _search_rects(page: pymupdf.Page, text: str) -> list[pymupdf.Rect]:
    needle = _normalize_search_text(text)
    if not needle:
        return []
    if _looks_like_phone_needle(text):
        by_digits = _search_rects_by_digits(page, text)
        if by_digits:
            return by_digits
    if _looks_like_iban_needle(text):
        found_iban: list[pymupdf.Rect] = []
        for group in _run_iban_word_groups(page, text):
            found_iban.extend(_union_rects_by_line(group))
        if found_iban:
            return found_iban
    whole_token = _single_token_word_groups(page, text)
    if whole_token:
        found_tokens: list[pymupdf.Rect] = []
        for group in whole_token:
            found_tokens.extend(_union_rects_by_line(group))
        if found_tokens:
            return found_tokens
    needle_tokens = needle.split()
    if (
        len(needle_tokens) == 1
        and any(char.isalpha() for char in needle_tokens[0])
        and _pdf_words(page)
    ):
        # Prefix search_for("Page") also hits "pages". Whole-token miss wins.
        return _search_rects_by_words(page, text)
    found = list(page.search_for(text)) or list(page.search_for(needle))
    if found:
        if _looks_like_phone_needle(text):
            covered = _digit_key("".join(page.get_textbox(rect) or "" for rect in found))
            if len(covered) < len(_digit_key(text)):
                by_digits = _search_rects_by_digits(page, text)
                if by_digits:
                    return by_digits
        return found
    parts: list[pymupdf.Rect] = []
    for part in re.split(r"[\n\r]+", text):
        part = _normalize_search_text(part)
        if len(part) >= 2:
            parts.extend(list(page.search_for(part) or []))
    if parts:
        return parts
    return _search_rects_by_words(page, text)


PAGE_PREVIEW_SCALE = 2.0


def render_page_png(page: pymupdf.Page, scale: float = PAGE_PREVIEW_SCALE) -> bytes:
    """Render a PDF page to PNG bytes for the review workspace."""
    clamped = min(max(scale, 0.5), 3.0)
    matrix = pymupdf.Matrix(clamped, clamped)
    pixmap = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)
    return pixmap.tobytes("png")


def render_job_page_png(job: Job, page_num: int, scale: float) -> bytes:
    """Rasterize one page, reusing the open PDF and PNG cache for this job."""
    cache_key = f"{page_num}:{float(scale):g}"
    cached = job.page_images.get(cache_key)
    if cached:
        return cached
    with job.page_render_lock:
        cached = job.page_images.get(cache_key)
        if cached:
            return cached
        document = job._pdf
        if document is None:
            document = _open_pdf(job.source_path)
            job._pdf = document
        if page_num < 0 or page_num >= document.page_count:
            raise IndexError("PAGE_NOT_FOUND")
        png_bytes = render_page_png(document[page_num], float(scale))
        job.page_images[cache_key] = png_bytes
        return png_bytes


def _compact_surface(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _page_may_hold_text(
    page_text: str,
    folded_page: str,
    compact_page: str,
    digit_page: str,
    needle: str,
) -> bool:
    """Cheap pre-filter so PDF search_for is not run on unrelated pages."""
    if not needle or not page_text:
        return False
    if needle in page_text:
        return True
    compact = _compact_surface(needle)
    if compact and compact in compact_page:
        return True
    folded = fold_tr_identity(needle)
    if folded and folded in folded_page:
        return True
    digits = re.sub(r"\D+", "", needle)
    if len(digits) >= 7 and digits in digit_page:
        return True
    return False


def _iban_overlay_rects(page: pymupdf.Page, text: str) -> list[pymupdf.Rect]:
    found: list[pymupdf.Rect] = []
    for group in _run_iban_word_groups(page, text):
        found.extend(_union_rects_by_line(group))
    if found:
        return found
    return _search_rects(page, text)


def collect_page_spans(job: Job) -> list[dict]:
    """Map detected entities to PDF page rectangles for the visual viewer."""
    if job.document_kind != DocumentKind.PDF or not job.analysis:
        return []
    document = pymupdf.open(str(job.source_path))
    try:
        search_cache: dict[tuple[int, str], list[pymupdf.Rect]] = {}

        def cached_search(page_num: int, text: str) -> list[pymupdf.Rect]:
            key = (page_num, _normalize_search_text(text))
            if key in search_cache:
                return search_cache[key]
            if page_num < 0 or page_num >= document.page_count:
                search_cache[key] = []
                return []
            found = _search_rects(document[page_num], text)
            search_cache[key] = found
            return found

        buckets: dict[int, dict[str, dict]] = {index: {} for index in range(document.page_count)}
        page_texts = job.page_texts
        folded_pages = [fold_tr_identity(text) for text in page_texts]
        compact_pages = [_compact_surface(text) for text in page_texts]
        digit_pages = [re.sub(r"\D+", "", text) for text in page_texts]

        def page_may_hold(page_num: int, needle: str) -> bool:
            if page_num < 0 or page_num >= len(page_texts):
                return True
            return _page_may_hold_text(
                page_texts[page_num],
                folded_pages[page_num],
                compact_pages[page_num],
                digit_pages[page_num],
                needle,
            )

        for entity in job.analysis.entities:
            if entity.rectangles:
                hits = [
                    (entity.page, pymupdf.Rect(item.x0, item.y0, item.x1, item.y1))
                    for item in entity.rectangles
                ]
                _store_span_hits(buckets, entity, hits)
                continue
            if entity.type == EntityType.UYAP_ACCESS and 0 <= entity.page < document.page_count:
                try:
                    uyap_rects = _uyap_access_rects(document[entity.page], entity.text)
                except (ValueError, TypeError, RuntimeError, OSError):
                    uyap_rects = []
                if uyap_rects:
                    _store_span_hits(buckets, entity, [(entity.page, rect) for rect in uyap_rects])
                    continue
            hits: list[tuple[int, pymupdf.Rect]] = [
                (entity.page, pymupdf.Rect(*span.rectangle))
                for span in job.span_boxes
                if span.page == entity.page
                and entity.start < span.end
                and entity.end > span.start
            ]
            if not hits and 0 <= entity.page < document.page_count:
                page = document[entity.page]
                if 0 <= entity.page < len(job.page_texts):
                    page_offset = sum(len(text) for text in job.page_texts[: entity.page])
                    ranked = _rect_for_entity(
                        page,
                        job.page_texts[entity.page],
                        entity.text,
                        entity.start - page_offset,
                        entity.end - page_offset,
                    )
                    hits = [(entity.page, rect) for rect in ranked]
                if not hits:
                    hits = [(entity.page, rect) for rect in cached_search(entity.page, entity.text)]
            if not hits:
                for page_num in range(document.page_count):
                    if page_num == entity.page:
                        continue
                    if not page_may_hold(page_num, entity.text):
                        continue
                    found = cached_search(page_num, entity.text)
                    if found:
                        hits = [(page_num, rect) for rect in found]
                        break
            _store_span_hits(buckets, entity, hits)
        pages = [
            {
                "page": page_num,
                "width": float(document[page_num].rect.width),
                "height": float(document[page_num].rect.height),
                "spans": list(buckets[page_num].values()),
                "line_rects": [
                    {
                        "x0": float(rect.x0),
                        "y0": float(rect.y0),
                        "x1": float(rect.x1),
                        "y1": float(rect.y1),
                    }
                    for rect in page_line_rects(document[page_num])
                ]
                if buckets[page_num]
                else [],
            }
            for page_num in range(document.page_count)
        ]
        _attach_court_mask_rects(job, document, pages)
        _attach_entity_font_sizes(job, document, pages)
        return pages
    finally:
        document.close()


def _store_span_hits(
    buckets: dict[int, dict[str, dict]],
    entity: EntityCandidate,
    hits: list[tuple[int, pymupdf.Rect]],
) -> None:
    for page_num, rect in hits:
        if page_num not in buckets:
            continue
        entry = buckets[page_num].setdefault(
            entity.id,
            {
                "entity_id": entity.id,
                "text": entity.text,
                "type": entity.type.value,
                "rectangles": [],
            },
        )
        entry["rectangles"].append(
            {
                "x0": float(rect.x0),
                "y0": float(rect.y0),
                "x1": float(rect.x1),
                "y1": float(rect.y1),
            }
        )


def _attach_court_mask_rects(job: Job, document: pymupdf.Document, pages: list[dict]) -> None:
    if not job.analysis:
        return
    by_id = {entity.id: entity for entity in job.analysis.entities}
    for page in pages:
        pdf_page = document[page["page"]]
        for span in page["spans"]:
            entity = by_id.get(span["entity_id"])
            if entity is None or entity.type != EntityType.COURT_NAME:
                continue
            if entity.attributes.get("mask_scope") == "header_line":
                continue
            court_rects = [
                pymupdf.Rect(item["x0"], item["y0"], item["x1"], item["y1"])
                for item in span["rectangles"]
            ]
            masks = _court_ordinal_rects(pdf_page, entity.text, court_rects, entity.attributes)
            if masks:
                span["mask_rectangles"] = [
                    {
                        "x0": float(rect.x0),
                        "y0": float(rect.y0),
                        "x1": float(rect.x1),
                        "y1": float(rect.y1),
                    }
                    for rect in masks
                ]


def _page_text_dict(page: pymupdf.Page, cache: dict[int, dict]) -> dict:
    number = _page_index(page)
    if number not in cache:
        try:
            payload: Any = page.get_text("dict")
            cache[number] = payload if isinstance(payload, dict) else {}
        except (ValueError, TypeError, RuntimeError, OSError):
            cache[number] = {}
    return cache[number]


def _median_font_size(
    page: pymupdf.Page,
    rectangles: list[pymupdf.Rect],
    cache: dict[int, dict],
) -> float | None:
    if not rectangles:
        return None
    sizes: list[float] = []
    for block in _page_text_dict(page, cache).get("blocks", []):
        for line in block.get("lines", []) if isinstance(block, dict) else []:
            for span in line.get("spans", []) if isinstance(line, dict) else []:
                if not isinstance(span, dict):
                    continue
                bbox = span.get("bbox")
                size = span.get("size")
                if not bbox or size is None:
                    continue
                try:
                    span_rect = pymupdf.Rect(bbox)
                    value = float(size)
                except (TypeError, ValueError):
                    continue
                if value < 4 or value > 72:
                    continue
                if any(span_rect.intersects(rect) for rect in rectangles):
                    sizes.append(value)
    if not sizes:
        return None
    sizes.sort()
    return sizes[len(sizes) // 2]


def _attach_entity_font_sizes(
    job: Job, document: pymupdf.Document, pages: list[dict]
) -> None:
    if not job.analysis:
        return
    by_id = {entity.id: entity for entity in job.analysis.entities}
    cache: dict[int, dict] = {}
    for page in pages:
        pdf_page = document[page["page"]]
        for span in page["spans"]:
            entity = by_id.get(span["entity_id"])
            if entity is None:
                continue
            rectangles = [
                pymupdf.Rect(item["x0"], item["y0"], item["x1"], item["y1"])
                for item in span.get("rectangles") or []
            ]
            size = _median_font_size(pdf_page, rectangles, cache)
            if size is None:
                continue
            entity.attributes = {**entity.attributes, "font_size": round(size, 1)}


def _rectangles_from_parameters(parameters: dict | None) -> list[pymupdf.Rect] | None:
    raw = (parameters or {}).get("rectangles")
    if not isinstance(raw, list) or not raw:
        return None
    rectangles: list[pymupdf.Rect] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            x0 = float(item["x0"])
            y0 = float(item["y0"])
            x1 = float(item["x1"])
            y1 = float(item["y1"])
        except (KeyError, TypeError, ValueError):
            continue
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        rectangles.append(pymupdf.Rect(x0, y0, x1, y1))
    return rectangles or None


def _job_page_spans(job: Job) -> list[dict]:
    if job.page_spans:
        return job.page_spans
    analysis = job.analysis
    if analysis is not None and analysis.page_spans:
        return analysis.page_spans
    return []


def _rectangles_from_page_spans(
    job: Job, entity_id: str, page: int | None = None
) -> list[pymupdf.Rect]:
    """Reuse reviewer overlay boxes so export matches what the user already saw."""
    found: list[pymupdf.Rect] = []
    for entry in _job_page_spans(job):
        if page is not None and entry.get("page") != page:
            continue
        for span in entry.get("spans") or []:
            if not isinstance(span, dict) or span.get("entity_id") != entity_id:
                continue
            parsed = _rectangles_from_parameters({"rectangles": span.get("rectangles")})
            if parsed:
                found.extend(parsed)
    return found


def _rectangles_for_entity(
    job: Job, document: pymupdf.Document, entity: EntityCandidate
) -> list[pymupdf.Rect]:
    if entity.rectangles:
        return [pymupdf.Rect(item.x0, item.y0, item.x1, item.y1) for item in entity.rectangles]
    overlay = _rectangles_from_page_spans(job, entity.id, entity.page)
    if overlay:
        return overlay
    page_ok = 0 <= entity.page < document.page_count
    if entity.type == EntityType.UYAP_ACCESS and page_ok:
        try:
            uyap_rects = _uyap_access_rects(document[entity.page], entity.text)
        except (ValueError, TypeError, RuntimeError, OSError):
            uyap_rects = []
        if uyap_rects:
            return uyap_rects
    ocr_rectangles = [
        pymupdf.Rect(*span.rectangle)
        for span in job.span_boxes
        if span.page == entity.page
        and entity.start < span.end
        and entity.end > span.start
    ]
    if ocr_rectangles:
        return ocr_rectangles
    if not page_ok:
        return []
    page = document[entity.page]
    if 0 <= entity.page < len(job.page_texts):
        page_offset = sum(len(text) for text in job.page_texts[: entity.page])
        ranked = _rect_for_entity(
            page,
            job.page_texts[entity.page],
            entity.text,
            entity.start - page_offset,
            entity.end - page_offset,
        )
        if ranked:
            return ranked
    found = _search_rects(page, entity.text)
    return found


def _rectangles_for_manual(
    job: Job, document: pymupdf.Document, page_number: int, value: str
) -> list[pymupdf.Rect]:
    page = document[page_number]
    page_offset = sum(len(text) for text in job.page_texts[:page_number])
    page_text = job.page_texts[page_number]
    ranges: list[tuple[int, int]] = []
    cursor = 0
    while True:
        found = page_text.find(value, cursor)
        if found < 0:
            break
        ranges.append((page_offset + found, page_offset + found + len(value)))
        cursor = found + max(1, len(value))
    ocr_rectangles = {
        span.rectangle
        for span in job.span_boxes
        if span.page == page_number
        and any(start < span.end and end > span.start for start, end in ranges)
    }
    if ocr_rectangles:
        return [pymupdf.Rect(*rectangle) for rectangle in ocr_rectangles]
    return list(page.search_for(value))


def plan_job_operations(job: Job, request: RedactionRequest) -> list[TransformOp]:
    if not job.analysis:
        raise DocumentError("ANALYSIS_REQUIRED")
    return build_operations(
        job.analysis.text,
        job.analysis.entities,
        request.decisions,
        request.category_defaults,
        request.manual_redactions,
        locale=request.locale,
        tag_locale=tag_locale_for_job(job),
        legacy_method=request.method,
        initials_font_size=request.initials_font_size,
        state=job.resolution_state,
    )


def preview_transformations(job: Job, request: RedactionRequest) -> PreviewResponse:
    operations = plan_job_operations(job, request)
    preview_ops = list(operations)
    text = job.analysis.text if job.analysis else ""
    preview_ops = sorted(preview_ops, key=lambda item: (item.start, -item.end))
    deduped: list[TransformOp] = []
    for operation in preview_ops:
        if any(operation.start < other.end and operation.end > other.start for other in deduped):
            continue
        deduped.append(operation)
    output = apply_operations(text, deduped)
    rebuild = requires_text_rebuild(deduped, job.document_kind == DocumentKind.PDF)
    warnings = ["TEXT_REBUILD_EXPORT"] if rebuild and job.document_kind == DocumentKind.PDF else []
    return PreviewResponse(
        text=output,
        operations=[
            PreviewOperation(
                entity_id=op.entity_id,
                category=op.category,
                strategy=op.strategy,
                start=op.start,
                end=op.end,
                replacement=op.replacement,
                export_path="text_rebuild" if rebuild else op.export_path,  # type: ignore[arg-type]
                ai_assisted=op.ai_assisted,
            )
            for op in deduped
        ],
        requires_text_rebuild=rebuild,
        warnings=warnings,
        placeholder_tokens=placeholder_tokens_for_operations(job, operations),
    )


def _strategy_summary(operations: list[TransformOp]) -> str:
    counts = Counter(op.strategy.value for op in operations)
    if not counts:
        return "NONE"
    if len(counts) == 1:
        return next(iter(counts))
    return "MIXED:" + ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def _kept_count(request: RedactionRequest, entities: list[EntityCandidate]) -> int:
    decided = {item.entity_id: item for item in request.decisions}
    kept = 0
    for entity in entities:
        decision = decided.get(entity.id)
        if decision is None:
            continue
        if decision.action == "KEEP" or decision.strategy == TransformationStrategy.KEEP:
            kept += 1
    return kept


def _kept_entities(
    entities: list[EntityCandidate], operations: list[TransformOp]
) -> list[EntityCandidate]:
    transformed = {op.entity_id for op in operations if op.entity_id}
    return [entity for entity in entities if entity.id not in transformed]


async def _residual_checks(
    *,
    output_text: str,
    output_pages: list[PageText],
    selected_entities: list[EntityCandidate],
    kept_entities: list[EntityCandidate],
    resolved_document_language: str | None = None,
) -> tuple[ValidationStatus, list[str]]:
    """Secondary detector rescan. Not proof that selected values are gone.

    Uses the already-resolved document language (``job.locale`` after analysis),
    not UI locale and not a fresh heuristic on transformed output.
    """
    del output_text
    locale_ids = locale_ids_for_document(resolved_document_language)
    output_candidates, _ = await run_in_threadpool(
        run_detectors, output_pages, locale_ids
    )
    transformed_types = {entity.type for entity in selected_entities}
    kept_counter = Counter((entity.type, entity.text) for entity in kept_entities)
    output_counter = Counter(
        (candidate.type, candidate.text) for candidate in output_candidates
    )
    residual_by_decision: dict[str, set[str]] = {"ACCEPT": set(), "REVIEW": set()}
    for candidate in output_candidates:
        if candidate.type not in transformed_types:
            continue
        if output_counter[(candidate.type, candidate.text)] <= kept_counter.get(
            (candidate.type, candidate.text), 0
        ):
            continue
        decision = str(candidate.attributes.get("scoring_decision") or "ACCEPT")
        if decision == "IGNORE":
            continue
        if decision == "REVIEW":
            residual_by_decision["REVIEW"].add(candidate.type.value)
        else:
            residual_by_decision["ACCEPT"].add(candidate.type.value)
    residual_messages: list[str] = []
    residual_status = ValidationStatus.PASS
    if residual_by_decision["ACCEPT"]:
        residual_status = ValidationStatus.WARNING
        residual_messages.append(
            "RESIDUAL_STRUCTURED:" + ",".join(sorted(residual_by_decision["ACCEPT"]))
        )
    if residual_by_decision["REVIEW"]:
        residual_status = ValidationStatus.WARNING
        residual_messages.append(
            "RESIDUAL_REVIEW:" + ",".join(sorted(residual_by_decision["REVIEW"]))
        )
    return residual_status, residual_messages


def _apply_analysis_warning(job: Job, validation: ValidationResult) -> ValidationResult:
    assert job.analysis
    if job.analysis.analysis_status not in {AnalysisStatus.PARTIAL, AnalysisStatus.FAILED}:
        return validation
    if validation.status == ValidationStatus.FAILED:
        return validation
    return merge_residual_messages(
        validation, ["ANALYSIS_INCOMPLETE"], ValidationStatus.WARNING
    )


def _worse_status(
    current: ValidationStatus, incoming: ValidationStatus
) -> ValidationStatus:
    rank = {
        ValidationStatus.PASS: 0,
        ValidationStatus.WARNING: 1,
        ValidationStatus.FAILED: 2,
    }
    return incoming if rank[incoming] > rank[current] else current


_OFFICIAL_FONT_FILES = {
    "times": ("times.ttf", "timesi.ttf", "Times New Roman.ttf", "LiberationSerif-Regular.ttf"),
    "arial": ("arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"),
    "calibri": ("calibri.ttf", "Calibri.ttf", "Carlito-Regular.ttf"),
    "cambria": ("cambria.ttf", "Cambria.ttf", "cambria.ttc", "Caladea-Regular.ttf"),
    "georgia": ("georgia.ttf", "Georgia.ttf"),
    "courier": ("cour.ttf", "Courier New.ttf", "LiberationMono-Regular.ttf"),
}

_PDF_FONT_FALLBACK = {
    "times": "tiro",
    "arial": "helv",
    "calibri": "helv",
    "cambria": "tiro",
    "georgia": "tiro",
    "courier": "cour",
}


def _font_search_dirs() -> list[Path]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    return [
        windir,
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts/truetype/liberation"),
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library" / "Fonts",
    ]


def _resolve_official_font(name: str | None) -> tuple[str | None, str]:
    key = (name or "times").strip().lower()
    fallback = _PDF_FONT_FALLBACK.get(key, "tiro")
    filenames = _OFFICIAL_FONT_FILES.get(key, _OFFICIAL_FONT_FILES["times"])
    for directory in _font_search_dirs():
        if not directory.is_dir():
            continue
        for filename in filenames:
            candidate = directory / filename
            if candidate.is_file():
                return str(candidate), fallback
    return None, fallback


def _initials_font_size(operation: TransformOp, entity: EntityCandidate, fallback: float = 11.0) -> float:
    params = operation.parameters or {}
    for raw in (params.get("font_size"), entity.attributes.get("font_size")):
        if raw is None:
            continue
        try:
            size = float(raw)
        except (TypeError, ValueError):
            continue
        if 4 <= size <= 72:
            return size
    return fallback


def _merge_rects_on_line(rectangles: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Join word boxes that sit on the same line so initials are drawn once."""
    if not rectangles:
        return []
    return _union_rects_by_line(
        [(rect.x0, rect.y0, rect.x1, rect.y1) for rect in rectangles]
    )


def _union_all_rects(rectangles: list[pymupdf.Rect]) -> pymupdf.Rect:
    combined = pymupdf.Rect(rectangles[0])
    for rect in rectangles[1:]:
        combined |= rect
    return combined


def _overlay_font_metrics(fontfile: str | None) -> tuple[float, float]:
    """Return (ascender, descender) as fractions of fontsize. Descender is negative."""
    try:
        font: Any = pymupdf.Font(fontfile=fontfile) if fontfile else pymupdf.Font("helv")
        ascender = float(getattr(font, "ascender", 0.8) or 0.8)
        descender = float(getattr(font, "descender", -0.2) or -0.2)
        if ascender > 0:
            return ascender, descender
    except Exception:
        pass
    return 0.8, -0.2


def overlay_text_origin(
    rectangle: pymupdf.Rect,
    text: str,
    *,
    fontfile: str | None,
    fontsize: float,
    align: int,
    origin_x: float | None = None,
    min_size: float = 4.0,
    max_width: float | None = None,
    vertical_center: bool = False,
) -> tuple[float, float, float]:
    """Return (x, baseline, size) for overlay text inside ``rectangle``."""
    floor = min(max(min_size, 2.0), 72.0)
    size = max(float(fontsize), floor)
    if max_width is None:
        size = min(size, max(floor, rectangle.height * 0.95))

    width = _overlay_text_width(text, fontfile, size)
    if max_width is not None and max_width > 0 and width > max_width:
        size = max(floor, size * (max_width / width))
        width = _overlay_text_width(text, fontfile, size)
    if align == pymupdf.TEXT_ALIGN_LEFT:
        x = (origin_x if origin_x is not None else rectangle.x0) + 0.3
    else:
        x = rectangle.x0 + max(0.0, (rectangle.width - width) / 2.0)
    if vertical_center:
        ascender, descender = _overlay_font_metrics(fontfile)
        cy = (rectangle.y0 + rectangle.y1) / 2.0
        baseline = cy + size * (ascender + descender) / 2.0
    else:
        baseline = rectangle.y0 + min(rectangle.height * 0.82, size * 0.85)
    return x, baseline, size


def _insert_overlay_text(
    page: pymupdf.Page,
    rectangle: pymupdf.Rect,
    text: str,
    *,
    fontfile: str | None,
    fontname: str,
    fontsize: float,
    color: tuple[float, float, float],
    align: int,
    origin_x: float | None = None,
    min_size: float = 4.0,
    max_width: float | None = None,
    vertical_center: bool = False,
) -> None:
    """Draw replacement text inside the cover box. Avoids textbox clipping."""
    x, baseline, size = overlay_text_origin(
        rectangle,
        text,
        fontfile=fontfile,
        fontsize=fontsize,
        align=align,
        origin_x=origin_x,
        min_size=min_size,
        max_width=max_width,
        vertical_center=vertical_center,
    )
    overlay_name = f"f-{Path(fontfile).stem}" if fontfile else fontname
    try:
        if fontfile:
            page.insert_text(
                (x, baseline),
                text,
                fontsize=size,
                color=color,
                fontfile=fontfile,
                fontname=overlay_name,
            )
        else:
            page.insert_text(
                (x, baseline),
                text,
                fontsize=size,
                color=color,
                fontname=fontname,
            )
    except Exception:
        page.insert_text((x, baseline), text, fontsize=size, color=color, fontname="helv")


def _overlay_text_width(
    text: str,
    fontfile: str | None,
    fontsize: float,
) -> float:
    if fontfile:
        try:
            font: Any = pymupdf.Font(fontfile=fontfile)
            return float(font.text_length(text, fontsize=fontsize))
        except Exception:
            pass
    return fontsize * max(len(text), 1) * 0.48


def _clamp_exploded_placeholder_rect(
    rect: pymupdf.Rect,
    original: str,
    fontsize: float,
) -> pymupdf.Rect:
    """Keep a runaway mapping from painting a white column through the page."""
    glyphs = max(len(re.sub(r"\s+", "", original or "")), 2)
    expected_w = glyphs * max(fontsize, 8.0) * 0.62 + 10.0
    expected_h = max(fontsize, 8.0) * 1.45
    x1 = rect.x1
    y1 = rect.y1
    if float(rect.width) > expected_w * 2.8:
        x1 = rect.x0 + expected_w
    if float(rect.height) > expected_h * 2.2:
        y1 = rect.y0 + expected_h
    if x1 == rect.x1 and y1 == rect.y1:
        return rect
    return pymupdf.Rect(rect.x0, rect.y0, x1, y1)


def _fit_placeholder_source(
    rect: pymupdf.Rect,
    page: pymupdf.Page,
    words: list[pymupdf.Rect],
    replacement: str,
    fontfile: str | None,
    fontsize: float,
    original: str,
) -> tuple[pymupdf.Rect, float]:
    """Keep the name box; shrink the tag so it never covers neighboring words."""
    source = _clamp_exploded_placeholder_rect(rect, original, fontsize)
    clipped = source & page.rect
    if not clipped.is_empty:
        source = clipped
    source = _clip_cover_to_words(source, source, words)
    size = max(float(fontsize), 2.8)
    if replacement == COURT_ORDINAL_TAG:
        size = min(size, max(2.8, float(source.height)))
    if not replacement:
        return source, size
    available = max(float(source.width) - 1.0, 2.0)
    needed = _overlay_text_width(replacement, fontfile, size) + 1.0
    if needed > available:
        size = max(2.0, size * (available / needed))
    return source, size


_MARKS_ABOVE = frozenset("İĞÖÜÔŐŰÄËŶÂÎÛíğöüôőűäëŷâîû")
_MARKS_BELOW = frozenset("ÇŞçş")
_BREVE_ABOVE = frozenset("ĞğĜĝ")
_COMBINING_BREVE = "\u0306"


def _has_breve(text: str) -> bool:
    """Ğ's breve sits well above the tight PDF glyph box; also catch G + combining mark."""
    if any(char in _BREVE_ABOVE for char in text):
        return True
    return _COMBINING_BREVE in unicodedata.normalize("NFD", text)


def _has_marks_above(text: str) -> bool:
    return any(char in _MARKS_ABOVE for char in text) or _has_breve(text)


def _clip_cover_to_words(
    cover: pymupdf.Rect,
    origin: pymupdf.Rect,
    words: list[pymupdf.Rect],
) -> pymupdf.Rect:
    """Keep placeholder covers out of neighboring glyphs (Mr / Counsel)."""
    x0 = cover.x0
    x1 = cover.x1
    line = max(origin.height, 8.0)
    center = (origin.y0 + origin.y1) / 2.0
    for other in words:
        other_center = (other.y0 + other.y1) / 2.0
        if abs(other_center - center) > line * 0.45:
            continue
        if other.x0 < origin.x1 - 0.5 and other.x1 > origin.x0 + 0.5:
            continue
        if other.x1 <= origin.x0 + 0.5:
            x0 = max(x0, other.x1 + 0.7)
        elif other.x0 >= origin.x1 - 0.5:
            x1 = min(x1, other.x0 - 0.7)
    if x1 <= x0 + 2:
        return origin
    return pymupdf.Rect(x0, cover.y0, x1, cover.y1)


def _expand_redact_rect(
    rect: pymupdf.Rect,
    clip: pymupdf.Rect,
    text: str = "",
    neighbors: list[pymupdf.Rect] | None = None,
    words: list[pymupdf.Rect] | None = None,
    tight_horiz: bool = False,
) -> pymupdf.Rect:
    """Cover diacritics in the inter-line gap; never enter the previous line box.

    PDF word boxes omit İ/Ü/Ğ/Ö marks. Grow the white cover upward into the
    leading between lines, then clip against neighboring line bottoms.
    PLACEHOLDER covers stay tight horizontally so honorifics and following
    role words remain visible.
    """
    height = max(float(rect.height), 8.0)
    if tight_horiz:
        horiz = 0.45
    else:
        horiz = max(1.6, min(3.2, height * 0.22))
    up = 2.4
    down = 1.4
    if _has_marks_above(text):
        up = 4.0
    if _has_breve(text):
        up = 6.2
    if any(char in _MARKS_BELOW for char in text):
        down = 2.6
    cover = pymupdf.Rect(
        rect.x0 - horiz,
        rect.y0 - up,
        rect.x1 + horiz,
        rect.y1 + down,
    )
    cover = _clip_cover_to_neighbors(cover, rect, neighbors or [])
    if words:
        cover = _clip_cover_to_words(cover, rect, words)
    clipped = cover & clip
    if clipped.is_empty or clipped.width < 1 or clipped.height < 1:
        return rect
    return clipped


def _clip_cover_to_neighbors(
    cover: pymupdf.Rect,
    origin: pymupdf.Rect,
    neighbors: list[pymupdf.Rect],
) -> pymupdf.Rect:
    """Keep the cover out of other lines' glyph boxes; the gap is usable."""
    y0 = cover.y0
    y1 = cover.y1
    center = (origin.y0 + origin.y1) / 2.0
    line = max(origin.height, 8.0)
    for other in neighbors:
        if other.x1 < origin.x0 - 4 or other.x0 > origin.x1 + 4:
            continue
        other_center = (other.y0 + other.y1) / 2.0
        if abs(other_center - center) < line * 0.45:
            continue
        if other_center < center:
            y0 = max(y0, other.y1 + 0.3)
            y0 = min(y0, origin.y0)
        else:
            y1 = min(y1, other.y0 - 0.3)
            y1 = max(y1, origin.y1)
    if y1 <= y0 + 2:
        return origin
    return pymupdf.Rect(cover.x0, y0, cover.x1, y1)


def _paint_paper_rect(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    fill: tuple[float, float, float],
) -> None:
    """Opaque paper patch with no stroke. Strokes show up as ink residue."""
    page.draw_rect(rect, color=None, fill=fill, width=0, overlay=True)


_STACKED_X_TOL = 14.0
_STACKED_MIN_DY = 0.45
_STACKED_MAX_DY = 2.4


def _is_next_stacked_row(first: pymupdf.Rect, second: pymupdf.Rect) -> bool:
    """True when two name boxes sit on consecutive column rows, not body lines."""
    if abs(first.x0 - second.x0) > _STACKED_X_TOL:
        return False
    line = max(first.height, second.height, 8.0)
    dy = abs((first.y0 + first.y1) / 2.0 - (second.y0 + second.y1) / 2.0)
    if dy < line * _STACKED_MIN_DY:
        return False
    return dy <= line * _STACKED_MAX_DY


def _stacked_initials_runs(
    items: list[tuple[str, int, pymupdf.Rect]],
) -> list[list[tuple[str, int, pymupdf.Rect]]]:
    """Consecutive same-x name rows only. Do not chain across the page."""
    by_page: dict[int, list[tuple[str, int, pymupdf.Rect]]] = defaultdict(list)
    for item in items:
        by_page[item[1]].append(item)
    runs: list[list[tuple[str, int, pymupdf.Rect]]] = []
    for group in by_page.values():
        ordered = sorted(group, key=lambda item: (item[2].y0 + item[2].y1) / 2.0)
        current: list[tuple[str, int, pymupdf.Rect]] = []
        for item in ordered:
            if current and _is_next_stacked_row(current[-1][2], item[2]):
                current.append(item)
                continue
            if len(current) >= 2:
                runs.append(current)
            current = [item]
        if len(current) >= 2:
            runs.append(current)
    return runs


def _stacked_initials_entity_ids(
    items: list[tuple[str, int, pymupdf.Rect]],
) -> set[str]:
    """Detect names stacked in a column (same left edge, consecutive lines)."""
    return {entity_id for run in _stacked_initials_runs(items) for entity_id, _page, _rect in run}


def _stacked_column_left(
    items: list[tuple[str, int, pymupdf.Rect]], stacked_ids: set[str]
) -> dict[str, float]:
    """Shared left edge per consecutive name run; body names keep their own x."""
    left_of: dict[str, float] = {}
    stacked_items = [item for item in items if item[0] in stacked_ids]
    for run in _stacked_initials_runs(stacked_items):
        origin = min(rect.x0 for _entity_id, _page, rect in run)
        for entity_id, _page, _rect in run:
            left_of[entity_id] = origin
    return left_of


def _is_transparent_fill(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"transparent", "none", "clear"}


def _fill_from_parameters(parameters: dict | None) -> tuple[float, float, float] | None:
    raw = (parameters or {}).get("fill")
    if not isinstance(raw, str) or _is_transparent_fill(raw):
        return None
    stripped = raw.strip().lstrip("#")
    if len(stripped) != 6:
        return None
    try:
        return (
            int(stripped[0:2], 16) / 255,
            int(stripped[2:4], 16) / 255,
            int(stripped[4:6], 16) / 255,
        )
    except ValueError:
        return None


def _hex_to_rgb(value: str | None, fallback: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if not value:
        return fallback
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (int(raw[0:2], 16) / 255, int(raw[2:4], 16) / 255, int(raw[4:6], 16) / 255)
    except ValueError:
        return fallback


_PAPER_REDACT_TYPES = frozenset({EntityType.QR_CODE, EntityType.UYAP_ACCESS, EntityType.PROFESSIONAL_ID})
_WHITE_RGB = (1.0, 1.0, 1.0)
_BLACK_RGB = (0.0, 0.0, 0.0)
_PAPER_LUMA_FLOOR = 540


def uses_paper_redaction(entity: EntityCandidate | None) -> bool:
    """QR codes, UYAP access, sicil numbers, and the court+docket header line use a paper fill."""
    if entity is None:
        return False
    if entity.type in _PAPER_REDACT_TYPES:
        return True
    return entity.attributes.get("mask_scope") == "header_line"


def _page_background_rgb(page: pymupdf.Page) -> tuple[float, float, float]:
    """Sample paper color from page corners; court PDFs are almost always white."""
    try:
        rect = page.rect
        inset = 8.0
        points = (
            (rect.x0 + inset, rect.y0 + inset),
            (rect.x1 - inset, rect.y0 + inset),
            (rect.x0 + inset, rect.y1 - inset),
            (rect.x1 - inset, rect.y1 - inset),
        )
        samples: list[tuple[int, int, int]] = []
        for x, y in points:
            clip = pymupdf.Rect(x, y, x + 2, y + 2)
            pixmap = page.get_pixmap(matrix=pymupdf.Identity, clip=clip, alpha=False)
            if pixmap.width > 0 and pixmap.height > 0:
                samples.append(pixmap.pixel(0, 0))
        if not samples:
            return _WHITE_RGB
        red, green, blue = max(samples, key=lambda rgb: rgb[0] + rgb[1] + rgb[2])
        if red + green + blue < _PAPER_LUMA_FLOOR:
            return _WHITE_RGB
        return (red / 255.0, green / 255.0, blue / 255.0)
    except (ValueError, TypeError, RuntimeError, OSError):
        return _WHITE_RGB


def _redaction_fill_rgb(
    page: pymupdf.Page,
    entity: EntityCandidate | None,
    strategy: TransformationStrategy,
    cache: dict[int, tuple[float, float, float]] | None = None,
) -> tuple[float, float, float]:
    if entity is not None and entity.type == EntityType.PROFESSIONAL_ID:
        return _WHITE_RGB
    if uses_paper_redaction(entity):
        page_number = _page_index(page)
        if cache is not None and page_number in cache:
            return cache[page_number]
        color = _page_background_rgb(page)
        if cache is not None:
            cache[page_number] = color
        return color
    return _BLACK_RGB


def _write_redacted_pdf(
    job: Job,
    request: RedactionRequest,
    operations: list[TransformOp],
    by_id: dict[str, EntityCandidate],
    skipped: list[str] | None = None,
) -> Path:
    """Burn redactions into a copy of the source PDF. Runs in a worker thread."""
    document = _open_pdf(job.source_path)
    unresolved: list[str] = []
    applied = 0
    used_manuals: set[int] = set()
    text_overlays: list[
        tuple[
            int,
            pymupdf.Rect,
            str,
            str | None,
            str,
            float,
            tuple[float, float, float],
            int,
            tuple[float, float, float] | None,
            pymupdf.Rect | None,
            float,
            float | None,
        ]
    ] = []
    background_cache: dict[int, tuple[float, float, float]] = {}
    initials_jobs: list[
        tuple[
            str,
            int,
            list[pymupdf.Rect],
            str,
            str | None,
            str,
            float,
            tuple[float, float, float],
            str,
            TransformationStrategy,
        ]
    ] = []
    try:
        for operation in operations:
            if operation.category == "MANUAL":
                # Find matching manual page via request.
                manual = None
                for index, item in enumerate(request.manual_redactions):
                    if index in used_manuals:
                        continue
                    if item.text == operation.original:
                        used_manuals.add(index)
                        manual = item
                        break
                page_number = manual.page if manual else 0
                page = document[page_number] if page_number < document.page_count else None
                if page is None:
                    unresolved.append(f"manual-page-{page_number}")
                    continue
                if manual and manual.rectangles:
                    rectangles = [
                        pymupdf.Rect(item.x0, item.y0, item.x1, item.y1)
                        for item in manual.rectangles
                    ]
                else:
                    rectangles = _rectangles_for_manual(
                        job, document, page_number, operation.original
                    )
                if not rectangles:
                    unresolved.append(f"manual-{page_number}")
                    continue
                fill = _hex_to_rgb(manual.fill if manual else None)
                clear_fill = _is_transparent_fill(manual.fill if manual else None)
                text_color = _hex_to_rgb(manual.text_color if manual else None, (0.07, 0.07, 0.09))
                replacement = (manual.replacement or "").strip() if manual else ""
                fontfile, fontname = _resolve_official_font(manual.font if manual else None)
                fontsize = float(manual.font_size or 11) if manual else 11.0
                for rectangle in rectangles:
                    if replacement:
                        if not clear_fill:
                            page.add_redact_annot(rectangle, fill=fill or (1, 1, 1))
                        text_overlays.append(
                            (
                                page_number,
                                rectangle,
                                replacement,
                                fontfile,
                                fontname,
                                fontsize,
                                text_color,
                                pymupdf.TEXT_ALIGN_CENTER,
                                None,
                                None,
                                4.0,
                                None,
                            )
                        )
                    else:
                        page.add_redact_annot(rectangle, fill=fill)
                applied += 1
                continue

            entity = by_id.get(operation.entity_id or "")
            if entity is None:
                unresolved.append(operation.entity_id or "unknown")
                continue
            if not (0 <= entity.page < document.page_count):
                unresolved.append(entity.id)
                continue
            page = document[entity.page]
            resized = _rectangles_from_parameters(operation.parameters)
            rectangles = resized or _rectangles_for_entity(job, document, entity)
            if not rectangles:
                unresolved.append(entity.id)
                continue
            if _ocr_mapping_coarse(job, entity):
                operation.mapping_coarse = True
            if (
                resized is None
                and entity.type == EntityType.COURT_NAME
                and operation.strategy
                in {
                    TransformationStrategy.PARTIAL_MASK,
                    TransformationStrategy.PLACEHOLDER,
                }
            ):
                rectangles = _court_ordinal_rects(page, entity.text, rectangles, entity.attributes)
                if not rectangles:
                    continue
            fill = _fill_from_parameters(operation.parameters) or _redaction_fill_rgb(
                page, entity, operation.strategy, background_cache
            )
            court_ordinal_tag = (
                entity.type == EntityType.COURT_NAME
                and operation.strategy == TransformationStrategy.PLACEHOLDER
            )
            overlay_text = (
                (
                    operation.strategy
                    in {
                        TransformationStrategy.INITIALS,
                        TransformationStrategy.PLACEHOLDER,
                    }
                    or (
                        operation.strategy == TransformationStrategy.PARTIAL_MASK
                        and entity.type != EntityType.COURT_NAME
                    )
                )
                and (operation.replacement or "").strip()
            )
            if overlay_text:
                page_number = _page_index(page)
                fill = background_cache.get(page_number) or _page_background_rgb(page)
                background_cache[page_number] = fill
                fontfile, fontname = _resolve_official_font("times")
                fontsize = _initials_font_size(operation, entity)
                merged = list(rectangles) if court_ordinal_tag else (
                    _merge_rects_on_line(rectangles) or list(rectangles)
                )
                overlay = COURT_ORDINAL_TAG if court_ordinal_tag else operation.replacement.strip()
                source_text = (
                    (court_ordinal(entity.text) or COURT_ORDINAL_TAG)
                    if court_ordinal_tag
                    else (operation.original or entity.text)
                )
                initials_jobs.append(
                    (
                        entity.id,
                        entity.page,
                        merged,
                        overlay,
                        fontfile,
                        fontname,
                        fontsize,
                        fill,
                        source_text,
                        operation.strategy,
                    )
                )
                applied += 1
                continue
            for rectangle in rectangles:
                page.add_redact_annot(rectangle, fill=fill)
            applied += 1

        stack_items = [
            (entity_id, page_number, _union_all_rects(rects))
            for entity_id, page_number, rects, *_ in initials_jobs
            if rects
        ]
        stacked_runs = _stacked_initials_runs(stack_items)
        stacked_ids = {
            entity_id for run in stacked_runs for entity_id, _page, _rect in run
        }
        run_neighbors: dict[str, list[pymupdf.Rect]] = {}
        for run in stacked_runs:
            for entity_id, _page, rect in run:
                run_neighbors[entity_id] = [
                    other_rect
                    for other_id, _p, other_rect in run
                    if other_id != entity_id
                ]
        line_cache: dict[int, list[pymupdf.Rect]] = {}
        word_cache: dict[int, list[pymupdf.Rect]] = {}
        for (
            entity_id,
            page_number,
            rects,
            replacement,
            fontfile,
            fontname,
            fontsize,
            fill,
            original,
            strategy,
        ) in initials_jobs:
            page = document[page_number]
            stacked = entity_id in stacked_ids
            placeholder = strategy in {
                TransformationStrategy.PLACEHOLDER,
                TransformationStrategy.PARTIAL_MASK,
            }
            align = (
                pymupdf.TEXT_ALIGN_LEFT
                if stacked and not placeholder
                else pymupdf.TEXT_ALIGN_CENTER
            )
            if page_number not in line_cache:
                line_cache[page_number] = page_line_rects(page)
            if page_number not in word_cache:
                word_cache[page_number] = [
                    pymupdf.Rect(item[0], item[1], item[2], item[3])
                    for item in _pdf_words(page)
                ]
            neighbors = list(run_neighbors.get(entity_id, []) if stacked else [])
            neighbors.extend(line_cache[page_number])
            for index, rectangle in enumerate(rects):
                source = rectangle
                draw_size = fontsize
                paint = replacement if index == 0 or replacement == COURT_ORDINAL_TAG else ""
                if placeholder:
                    source, draw_size = _fit_placeholder_source(
                        rectangle,
                        page,
                        word_cache[page_number],
                        paint,
                        fontfile,
                        fontsize,
                        original,
                    )
                expanded = _expand_redact_rect(
                    source,
                    page.rect,
                    f"{original} {replacement}",
                    neighbors,
                    words=word_cache[page_number] if placeholder else None,
                    tight_horiz=placeholder,
                )
                page.add_redact_annot(expanded, fill=fill)
                max_width = float(source.width) if placeholder else None
                text_overlays.append(
                    (
                        page_number,
                        expanded,
                        paint,
                        fontfile,
                        fontname,
                        draw_size,
                        (0.07, 0.07, 0.09),
                        align,
                        fill,
                        source,
                        2.8 if placeholder else 4.0,
                        max_width,
                    )
                )

        if unresolved:
            if applied == 0:
                raise DocumentError("SPAN_MAPPING_FAILED")
            if skipped is not None:
                skipped.extend(unresolved)
        for page_number in range(document.page_count):
            document[page_number].apply_redactions(images=REDACT_IMAGE_PIXELS)
        for (
            page_number,
            rectangle,
            text,
            fontfile,
            fontname,
            fontsize,
            color,
            align,
            cover,
            source_rect,
            min_size,
            max_width,
        ) in text_overlays:
            if cover is None:
                continue
            page = document[page_number]
            _paint_paper_rect(page, rectangle, cover)
        for (
            page_number,
            rectangle,
            text,
            fontfile,
            fontname,
            fontsize,
            color,
            align,
            cover,
            source_rect,
            min_size,
            max_width,
        ) in text_overlays:
            if not text:
                continue
            page = document[page_number]
            centered = max_width is not None
            box = rectangle if centered else (source_rect or rectangle)
            _insert_overlay_text(
                page,
                box,
                text,
                fontfile=fontfile,
                fontname=fontname,
                fontsize=fontsize,
                color=color,
                align=align,
                origin_x=box.x0 if align == pymupdf.TEXT_ALIGN_LEFT else None,
                min_size=min_size,
                max_width=max_width,
                vertical_center=centered,
            )
        output_path = job.directory / "redacted.pdf"
        document.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        document.close()
    return output_path


def _read_redacted_pdf(job: Job, output_path: Path) -> tuple[list[PageText], str]:
    """Re-extract the exported PDF for validation. Runs in a worker thread."""
    output = _open_pdf(output_path)
    try:
        if job.span_boxes:
            try:
                output_pages, output_text, _, _ = extract_pdf_with_ocr(output)
            except Exception as exc:
                raise DocumentError("VALIDATION_FAILED") from exc
            return output_pages, output_text
        return _extract_pages(output)
    finally:
        output.close()


async def _secure_pdf_redact(
    job: Job,
    request: RedactionRequest,
    operations: list[TransformOp],
    ai_provider: object | None = None,
) -> tuple[Path, AuditReport]:
    assert job.analysis
    by_id = {entity.id: entity for entity in job.analysis.entities}
    selected = [
        by_id[op.entity_id]
        for op in operations
        if op.entity_id and op.entity_id in by_id
    ]

    skipped: list[str] = []
    output_path = await run_in_threadpool(
        _write_redacted_pdf, job, request, operations, by_id, skipped
    )
    output_pages, output_text = await run_in_threadpool(
        _read_redacted_pdf, job, output_path
    )

    kept = _kept_entities(job.analysis.entities, operations)
    kept_texts = [entity.text for entity in kept]
    validation = validate_operations(output_text, operations, kept_texts=kept_texts)
    validation = soften_pdf_text_residuals(validation)
    residual_status, residual_messages = await _residual_checks(
        output_text=output_text,
        output_pages=output_pages,
        selected_entities=selected,
        kept_entities=kept,
        resolved_document_language=job.locale,
    )
    validation = merge_residual_messages(validation, residual_messages, residual_status)
    if skipped:
        validation = merge_residual_messages(
            validation, ["SPAN_MAPPING_PARTIAL"], ValidationStatus.WARNING
        )
    validation = _apply_analysis_warning(job, validation)
    return _finalize_audit(
        job,
        request,
        operations,
        validation,
        output_path,
        output_format="PDF",
        export_path="secure_pdf",
        media_type="application/pdf",
        output_name=f"redacted-{job.source_path.stem}.pdf",
        output_mode="original_layout",
        source_text_extraction_method=_extraction_method(job),
    )


def _write_and_read_output(text: str, path: Path, output_format: str) -> str:
    """Write the rebuilt output then read it back. Runs in a worker thread."""
    write_text_output(text, path, output_format)
    return extract_generated_output(path, output_format)


async def _text_rebuild_export(
    job: Job,
    request: RedactionRequest,
    operations: list[TransformOp],
    ai_provider: object | None = None,
) -> tuple[Path, AuditReport]:
    assert job.analysis
    by_id = {entity.id: entity for entity in job.analysis.entities}
    selected = [
        by_id[op.entity_id]
        for op in operations
        if op.entity_id and op.entity_id in by_id
    ]

    if job.document_kind == DocumentKind.PDF:
        output_format = "PDF"
    elif job.document_kind == DocumentKind.DOCX:
        output_format = "DOCX"
    else:
        output_format = request.output_format or "TXT"
        if output_format not in {"TXT", "PDF"}:
            raise DocumentError("OUTPUT_FORMAT_INVALID")

    if job.document_kind == DocumentKind.DOCX and output_format != "DOCX":
        raise DocumentError("OUTPUT_FORMAT_INVALID")

    redacted_text = await run_in_threadpool(
        apply_operations, job.analysis.text, operations
    )
    suffix = output_format.lower()
    output_path = job.directory / f"redacted.{suffix}"
    try:
        extracted_output = await run_in_threadpool(
            _write_and_read_output, redacted_text, output_path, output_format
        )
    except Exception as exc:
        raise DocumentError("REDACTION_OUTPUT_FAILED") from exc

    output_pages = [PageText(page=0, text=extracted_output, document_offset=0)]
    kept = _kept_entities(job.analysis.entities, operations)
    kept_texts = [entity.text for entity in kept]
    validation = validate_operations(extracted_output, operations, kept_texts=kept_texts)
    residual_status, residual_messages = await _residual_checks(
        output_text=extracted_output,
        output_pages=output_pages,
        selected_entities=selected,
        kept_entities=kept,
        resolved_document_language=job.locale,
    )
    validation = merge_residual_messages(validation, residual_messages, residual_status)
    validation = _apply_analysis_warning(job, validation)

    media = {
        "TXT": "text/plain; charset=utf-8",
        "PDF": "application/pdf",
        "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[output_format]
    if job.document_kind == DocumentKind.DOCX:
        name = f"redacted-{job.source_path.stem}.{suffix}"
    elif job.document_kind == DocumentKind.PDF:
        name = f"redacted-{job.source_path.stem}-rebuilt.{suffix}"
    else:
        name = f"redacted-text.{suffix}"
    return _finalize_audit(
        job,
        request,
        operations,
        validation,
        output_path,
        output_format=output_format,
        export_path="text_rebuild",
        media_type=media,
        output_name=name,
        output_mode="original_layout",
        source_text_extraction_method=_extraction_method(job),
    )


def _extraction_method(job: Job) -> str:
    if job.analysis and "OCR_USED" in job.analysis.warnings:
        return "ocr"
    return "native"


def _finalize_audit(
    job: Job,
    request: RedactionRequest,
    operations: list[TransformOp],
    validation: ValidationResult,
    output_path: Path,
    *,
    output_format: str,
    export_path: str,
    media_type: str,
    output_name: str,
    output_mode: str = "original_layout",
    source_text_extraction_method: str | None = None,
    content_integrity_validation: str | None = None,
    privacy_validation: str | None = None,
) -> tuple[Path, AuditReport]:
    assert job.analysis
    selected_categories = [
        op.category for op in operations if op.category and op.category != "MANUAL"
    ]
    audit = AuditReport(
        application_version=APP_VERSION,
        policy_version=POLICY_VERSION,
        document_hash=job.analysis.document_hash,
        document_kind=job.document_kind,
        output_format=output_format,
        privacy_profile=job.analysis.profile,
        detection_mode=job.analysis.detection_mode,
        detectors_executed=job.analysis.detectors_executed,
        detected_category_counts=dict(
            Counter(entity.type.value for entity in job.analysis.entities)
        ),
        redacted_category_counts=dict(Counter(selected_categories)),
        kept_count=_kept_count(request, job.analysis.entities),
        manual_redaction_count=len(request.manual_redactions),
        redaction_method=_strategy_summary(operations),
        strategy_counts=dict(Counter(op.strategy.value for op in operations)),
        export_path=export_path,  # type: ignore[arg-type]
        output_mode=output_mode,  # type: ignore[arg-type]
        source_text_extraction_method=source_text_extraction_method,  # type: ignore[arg-type]
        content_integrity_validation=content_integrity_validation,  # type: ignore[arg-type]
        privacy_validation=privacy_validation,  # type: ignore[arg-type]
        transformations=build_transformation_audit(operations, validation),
        validation=validation,
        analysis_status=job.analysis.analysis_status,
        ai_status=job.analysis.ai_status,
        analysis_warnings=list(job.analysis.warnings),
    )
    job.output_path = output_path
    job.output_name = output_name
    job.output_media_type = media_type
    job.audit = audit
    return output_path, audit


async def apply_transformations(
    job: Job,
    request: RedactionRequest,
    ai_provider: object | None = None,
) -> tuple[Path, AuditReport]:
    if not job.analysis:
        raise DocumentError("ANALYSIS_REQUIRED")

    # Ensure contextual rewrite decisions are present before planning ops that need them.
    operations = plan_job_operations(job, request)

    if not operations:
        raise DocumentError("NO_TRANSFORMATIONS_SELECTED")

    rebuild = requires_text_rebuild(operations, job.document_kind == DocumentKind.PDF)
    if job.document_kind == DocumentKind.PDF and not rebuild:
        return await _secure_pdf_redact(job, request, operations, ai_provider)
    return await _text_rebuild_export(job, request, operations, ai_provider)


# Backward-compatible names used by main.py and tests.
async def redact_pdf(
    job: Job,
    request: RedactionRequest,
    ai_provider: object | None = None,
) -> tuple[Path, AuditReport]:
    return await apply_transformations(job, request, ai_provider)


async def redact_textual_document(
    job: Job,
    request: RedactionRequest,
    ai_provider: object | None = None,
) -> tuple[Path, AuditReport]:
    return await apply_transformations(job, request, ai_provider)


def persist_job_outputs(job: Job, output_directory: str) -> tuple[Path, Path]:
    if not job.output_path or not job.audit or not job.output_name:
        raise DocumentError("OUTPUT_NOT_AVAILABLE")
    destination = Path(output_directory).expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = Path(job.output_name).stem
    suffix = Path(job.output_name).suffix
    saved_output = destination / f"{stem}-{timestamp}-{job.id[:8]}{suffix}"
    saved_audit = destination / f"{stem}-{timestamp}-{job.id[:8]}.audit.json"
    shutil.copy2(job.output_path, saved_output)
    saved_audit.write_text(
        json.dumps(job.audit.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    job.saved_output_path = saved_output
    job.saved_audit_path = saved_audit
    return saved_output, saved_audit
