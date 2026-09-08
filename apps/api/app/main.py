from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.domain.models import (
    DetectionMode,
    DocumentKind,
    EntityMatchRequest,
    PreviewRequest,
    PrivacyProfile,
    ProfileUpdateRequest,
    ReclassifyRequest,
    RedactionRequest,
    CustomTermsRequest,
    TransformationStrategy,
    UserDefinedTerm,
)
from app.domain.scan_mode import resolve_product_analyze_mode
from app.language.resolve import normalize_requested_language
from app.policy.engine import apply_policy
from app.transforms.resolution import assign_resolved_entities
from app.transforms.entity_merge import (
    confirm_entity_merge,
    reclassify_entities,
    reject_entity_match,
)
from app.transforms.possible_matches import generate_possible_matches
from app.transforms.tag_registry import (
    bind_canonical_ids,
    stamp_placeholder_tokens,
    tag_locale_for_job,
)
from app.services.jobs import JobStore
from app.services.pipeline import (
    DocumentError,
    analyze_pdf,
    analyze_textual_document,
    add_custom_terms_to_analysis,
    apply_transformations,
    collect_page_spans,
    render_job_page_png,
    persist_job_outputs,
    preview_transformations,
)
from app.transforms.catalog import build_catalog

settings = get_settings()
jobs = JobStore(settings.redaction_job_ttl_seconds)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for job_id in list(jobs._jobs):
        jobs.delete(job_id)


app = FastAPI(
    title="Local Legal Redaction API",
    version="0.2.2",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "ocr": "rapidocr-local",
        "output_directory": settings.redaction_output_dir,
    }


@app.get("/api/transforms/catalog")
def transforms_catalog() -> dict:
    return build_catalog()


@app.get("/api/locales")
def list_locales() -> dict:
    """List available locale packs for detection."""
    from app.detectors.registry import _ensure_packs_registered
    from app.detectors.locale_pack import list_locale_packs

    _ensure_packs_registered()
    packs = list_locale_packs()
    return {
        "locales": [
            {
                "id": pack.locale_id,
                "name": pack.name,
                "detector_count": len(pack.detectors),
            }
            for pack in packs
        ]
    }


def _parse_json_form(raw: str | None, label: str):
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"INVALID_{label}") from exc


@app.post("/api/documents/analyze")
async def analyze(
    file: UploadFile = File(...),
    profile: PrivacyProfile = Form(PrivacyProfile.GENERAL),
    mode: DetectionMode | None = Form(None),
    custom_terms: str | None = Form(None),
    scan_types: str | None = Form(None),
    document_language: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(400, "FILE_NAME_REQUIRED")
    extension = file.filename.lower().rsplit(".", 1)[-1]
    if extension not in {"pdf", "docx"}:
        raise HTTPException(415, "DOCUMENT_FORMAT_UNSUPPORTED")
    limit = settings.redaction_max_file_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "FILE_TOO_LARGE")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(400, "INVALID_PDF")
    if extension == "docx" and not content.startswith(b"PK"):
        raise HTTPException(400, "INVALID_DOCX")
    resolved_mode = resolve_product_analyze_mode(mode)
    kind = DocumentKind.PDF if extension == "pdf" else DocumentKind.DOCX
    job = jobs.create(file.filename, content, kind)
    if document_language and document_language.strip():
        raw = document_language.strip()
        normalized = normalize_requested_language(raw)
        job.requested_document_language = normalized or raw.strip().lower()
        if normalized in {"tr", "en"}:
            job.locale = normalized
    parsed_terms = _parse_json_form(custom_terms, "CUSTOM_TERMS")
    request_terms: list[UserDefinedTerm] = []
    if isinstance(parsed_terms, list):
        request_terms = [UserDefinedTerm.model_validate(item) for item in parsed_terms]
    job.custom_terms = request_terms
    parsed_scope = _parse_json_form(scan_types, "SCAN_TYPES")
    if isinstance(parsed_scope, list):
        job.scan_types = [str(item) for item in parsed_scope]
    try:
        if kind == DocumentKind.PDF:
            return await analyze_pdf(job, profile, None, resolved_mode)
        return await analyze_textual_document(job, profile, None, resolved_mode)
    except DocumentError as exc:
        jobs.delete(job.id)
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/jobs/{job_id}/custom-terms")
async def add_custom_terms(job_id: str, request: CustomTermsRequest):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    try:
        return await run_in_threadpool(add_custom_terms_to_analysis, job, request.terms)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/jobs/{job_id}/reanalyze")
async def reanalyze(job_id: str, profile: PrivacyProfile | None = None):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    next_profile = profile or job.analysis.profile
    mode = job.analysis.detection_mode
    try:
        if job.document_kind == DocumentKind.PDF:
            return await analyze_pdf(job, next_profile, None, mode)
        return await analyze_textual_document(job, next_profile, None, mode)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/jobs/{job_id}/profile")
async def update_profile(job_id: str, request: ProfileUpdateRequest):
    """Re-apply recommendation policy without re-running detection."""
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")

    entities = apply_policy(
        assign_resolved_entities(
            [entity.model_copy(deep=True) for entity in job.analysis.entities]
        ),
        request.profile,
        locale=job.locale,
    )
    entities = bind_canonical_ids(entities, job.resolution_state)
    entities = stamp_placeholder_tokens(
        entities, tag_locale_for_job(job), state=job.resolution_state
    )
    job.analysis = job.analysis.model_copy(
        update={
            "profile": request.profile,
            "entities": entities,
            "possible_matches": generate_possible_matches(
                entities, job.analysis.text, job.resolution_state
            ),
            "resolution_state": job.resolution_state,
        }
    )
    return job.analysis


@app.post("/api/jobs/{job_id}/entity-matches/merge")
async def merge_entity_match(job_id: str, request: EntityMatchRequest):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    try:
        return await run_in_threadpool(confirm_entity_merge, job, request.entity_ids)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/jobs/{job_id}/entity-matches/reject")
async def reject_entity_match_route(job_id: str, request: EntityMatchRequest):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    try:
        return await run_in_threadpool(reject_entity_match, job, request.entity_ids)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/jobs/{job_id}/entities/reclassify")
async def reclassify_job_entities(job_id: str, request: ReclassifyRequest):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    try:
        return await run_in_threadpool(
            reclassify_entities, job, request.entity_ids, request.entity_type
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/jobs/{job_id}/preview")
async def preview(job_id: str, request: PreviewRequest):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    redaction = RedactionRequest(
        decisions=request.decisions,
        category_defaults=request.category_defaults,
        manual_redactions=request.manual_redactions,
        method=request.method,
        locale=request.locale,
        initials_font_size=request.initials_font_size,
    )
    try:
        return await run_in_threadpool(preview_transformations, job, redaction)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/jobs/{job_id}/risk-assessment")
async def assess_risk(job_id: str, request: PreviewRequest):
    """Assess re-identification risk based on user decisions."""
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    
    from app.privacy.reidentification import assess_reidentification_risk
    
    # Build decisions map
    decisions_map = {}
    for decision in request.decisions:
        strategy = decision.strategy or (
            TransformationStrategy.KEEP if decision.action == "KEEP" 
            else TransformationStrategy.REDACT
        )
        decisions_map[decision.entity_id] = (decision.action, strategy)
    
    risk = assess_reidentification_risk(job.analysis.entities, decisions_map)
    
    return {
        "risk_level": risk.risk_level,
        "score": risk.score,
        "remaining_direct_identifiers": risk.remaining_direct_identifiers,
        "remaining_quasi_identifiers": risk.remaining_quasi_identifiers,
        "direct_identifier_types": risk.direct_identifier_types,
        "quasi_identifier_types": risk.quasi_identifier_types,
        "warnings": risk.warnings,
        "recommendations": risk.recommendations,
    }


@app.post("/api/jobs/{job_id}/redact")
async def redact(job_id: str, request: RedactionRequest):
    try:
        job = jobs.get(job_id)
        _, audit = await apply_transformations(job, request, None)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    except DocumentError as exc:
        logger.exception("POST /redact failed: %s", exc)
        raise HTTPException(422, str(exc)) from exc

    response = {
        "validation": audit.validation,
        "audit_url": f"/api/jobs/{job_id}/audit",
        "download_url": f"/api/jobs/{job_id}/download",
        "export_path": audit.export_path,
        "strategy_counts": audit.strategy_counts,
        "analysis_status": audit.analysis_status,
        "ai_status": audit.ai_status,
    }
    try:
        saved_output, saved_audit = await run_in_threadpool(
            persist_job_outputs, job, settings.redaction_output_dir
        )
        response["saved_path"] = str(saved_output)
        response["saved_audit_path"] = str(saved_audit)
    except (OSError, DocumentError) as exc:
        raise HTTPException(500, "AUTOMATIC_SAVE_FAILED") from exc
    return JSONResponse(content=_jsonable(response))


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


@app.get("/api/jobs/{job_id}/pages/{page_num}")
def get_page_image(job_id: str, page_num: int, scale: float = 1.5):
    """Render a PDF page as PNG for the visual document viewer."""
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if job.document_kind != DocumentKind.PDF:
        raise HTTPException(400, "NOT_A_PDF")
    if not job.source_path.exists():
        raise HTTPException(404, "JOB_NOT_FOUND")
    try:
        png_bytes = render_job_page_png(job, page_num, float(scale))
    except IndexError as exc:
        raise HTTPException(404, "PAGE_NOT_FOUND") from exc
    except (OSError, ValueError, RuntimeError, DocumentError) as exc:
        raise HTTPException(500, "PAGE_RENDER_FAILED") from exc
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.get("/api/jobs/{job_id}/spans")
def get_job_spans(job_id: str):
    """Bounding boxes for entities on each PDF page, in PDF point coordinates."""
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if job.document_kind != DocumentKind.PDF:
        raise HTTPException(400, "NOT_A_PDF")
    if not job.analysis:
        raise HTTPException(409, "ANALYSIS_REQUIRED")
    if not job.page_spans:
        job.page_spans = collect_page_spans(job)
    return {"pages": job.page_spans}


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.output_path or not job.output_path.exists():
        raise HTTPException(409, "OUTPUT_NOT_AVAILABLE")
    return FileResponse(
        job.output_path,
        media_type=job.output_media_type or "application/octet-stream",
        filename=job.output_name or f"redacted-{job.source_path.name}",
    )


@app.get("/api/jobs/{job_id}/audit")
def audit(job_id: str):
    try:
        job = jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "JOB_NOT_FOUND") from exc
    if not job.audit:
        raise HTTPException(409, "AUDIT_NOT_AVAILABLE")
    return JSONResponse(
        content=job.audit.model_dump(mode="json"),
        headers={"Content-Disposition": 'attachment; filename="audit-report.json"'},
    )


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    jobs.delete(job_id)
