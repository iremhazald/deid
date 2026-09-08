from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class EntityType(StrEnum):
    PERSON_NAME = "PERSON_NAME"
    FIRST_NAME = "FIRST_NAME"
    LAST_NAME = "LAST_NAME"
    ALIAS = "ALIAS"
    NATIONAL_ID = "NATIONAL_ID"
    PASSPORT_NUMBER = "PASSPORT_NUMBER"
    TAX_IDENTIFIER = "TAX_IDENTIFIER"
    EMPLOYEE_ID = "EMPLOYEE_ID"
    CUSTOMER_ID = "CUSTOMER_ID"
    ADDRESS = "ADDRESS"
    EMAIL = "EMAIL"
    PHONE_NUMBER = "PHONE_NUMBER"
    POSTAL_CODE = "POSTAL_CODE"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    IBAN = "IBAN"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    FINANCIAL_IDENTIFIER = "FINANCIAL_IDENTIFIER"
    SALARY_INFORMATION = "SALARY_INFORMATION"
    POLITICAL_INFORMATION = "POLITICAL_INFORMATION"
    COURT_NAME = "COURT_NAME"
    CASE_NUMBER = "CASE_NUMBER"
    FILE_NUMBER = "FILE_NUMBER"
    DECISION_NUMBER = "DECISION_NUMBER"
    JUDGE_NAME = "JUDGE_NAME"
    LAWYER_NAME = "LAWYER_NAME"
    CLAIMANT_NAME = "CLAIMANT_NAME"
    DEFENDANT_NAME = "DEFENDANT_NAME"
    WITNESS_NAME = "WITNESS_NAME"
    EXPERT_NAME = "EXPERT_NAME"
    SIGNATURE = "SIGNATURE"
    QR_CODE = "QR_CODE"
    UYAP_ACCESS = "UYAP_ACCESS"
    COMPANY_NAME = "COMPANY_NAME"
    ORGANISATION = "ORGANISATION"
    LOCATION = "LOCATION"
    DATE = "DATE"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    BIRTH_PLACE = "BIRTH_PLACE"
    VEHICLE_PLATE = "VEHICLE_PLATE"
    PROFESSIONAL_ID = "PROFESSIONAL_ID"
    PORT_NUMBER = "PORT_NUMBER"
    MONEY_AMOUNT = "MONEY_AMOUNT"
    SYSTEM_URL = "SYSTEM_URL"
    UETS = "UETS"
    OTHER_IDENTIFIER = "OTHER_IDENTIFIER"


class DetectionMethod(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    STRUCTURAL = "STRUCTURAL"
    AI = "AI"
    MANUAL = "MANUAL"


class VerificationLevel(StrEnum):
    """Deterministic strength of a finding. Not a confidence percentage."""

    VALIDATED = "validated"
    REVIEW_RECOMMENDED = "review_recommended"


class DetectionMode(StrEnum):
    """Internal detection strategy.

    RULES_ONLY — deterministic only. Fallback, tests, and environments
    without Local NER. Not a primary UI choice.
    LOCAL_CONTEXT — normal product scan: deterministic + on-device NER.
    """
    RULES_ONLY = "RULES_ONLY"
    LOCAL_CONTEXT = "LOCAL_CONTEXT"


class LocalNERStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    LOADED = "LOADED"
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class AnalysisStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class AIRunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    SUCCESS_ZERO = "SUCCESS_ZERO"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    SKIPPED = "SKIPPED"


class PrivacyProfile(StrEnum):
    GENERAL = "GENERAL"
    GDPR = "GDPR"
    KVKK = "KVKK"
    GDPR_KVKK = "GDPR_KVKK"
    CUSTOM = "CUSTOM"


class DocumentKind(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    TEXT = "TEXT"


class TransformationStrategy(StrEnum):
    REDACT = "REDACT"
    PLACEHOLDER = "PLACEHOLDER"
    INITIALS = "INITIALS"
    PARTIAL_MASK = "PARTIAL_MASK"
    KEEP = "KEEP"


class DecisionSource(StrEnum):
    DEFAULT = "default"
    USER_OVERRIDE = "user_override"
    OCCURRENCE_OVERRIDE = "occurrence_override"


class ManualRect(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class EntityRelation(BaseModel):
    """Directed link between two detected spans. Not shown in the review UI."""

    kind: str
    target_start: int | None = None
    target_end: int | None = None
    target_type: str | None = None
    target_text: str | None = None
    label: str | None = None


class EntityCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str = Field(min_length=1)
    type: EntityType
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    page: int = Field(ge=0)
    detector: str
    method: DetectionMethod
    validated: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    role: str | None = None
    reason: str | None = None
    recommended: bool = False
    resolved_entity_id: str | None = None
    role_confident: bool = False
    recommended_strategy: TransformationStrategy | None = None
    needs_review: bool = False
    verification_level: VerificationLevel | None = None
    verification_method: str | None = None
    rectangles: list[ManualRect] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    relations: list[EntityRelation] = Field(default_factory=list)
    placeholder_token: str | None = None

    @field_validator("end")
    @classmethod
    def offsets_are_valid(cls, value: int, info: ValidationInfo) -> int:
        start = info.data.get("start")
        if isinstance(start, int) and value <= start:
            raise ValueError("end must be greater than start")
        return value


class DetectionStats(BaseModel):
    deterministic: int = 0
    structural: int = 0
    ai_raw: int = 0
    after_schema: int = 0
    after_dedup: int = 0
    after_resolution: int = 0
    returned: int = 0
    ai_chunks: int = 0
    ai_chunks_failed: int = 0


ReviewResultStatus: TypeAlias = Literal[
    "NOT_CALLED",
    "RESOLVED",
    "UNRESOLVED",
    "FAILED",
    "UNAVAILABLE",
]


class RoutingMetadata(BaseModel):
    provider: str | None = None
    efficient_model: str | None = None
    review_model: str | None = None
    review_available: bool = False
    efficient_model_used: bool = False
    review_model_used: bool = False
    candidate_count: int = 0
    escalated_count: int = 0
    unresolved_count: int = 0
    escalation_reasons: list[str] = Field(default_factory=list)
    review_result: ReviewResultStatus = "NOT_CALLED"
    schema_success: bool = True
    detection_failed: bool = False
    error_code: str | None = None
    error_message: str | None = None
    http_status: int | None = None
    efficient_latency_ms: float | None = None
    review_latency_ms: float | None = None
    model_calls: int = 0
    pipeline_stats: DetectionStats | None = None


class PossibleMatchMember(BaseModel):
    canonical_id: str
    entity_ids: list[str] = Field(default_factory=list)
    text: str
    pages: list[int] = Field(default_factory=list)
    placeholder_token: str | None = None


class PossibleMatch(BaseModel):
    """User-facing merge suggestion. Never an automatic identity merge."""

    id: str
    members: list[PossibleMatchMember] = Field(default_factory=list)
    kind: Literal["person", "address"] = "person"


class ResolutionState(BaseModel):
    """Job-scoped merge / rejection / numbering order. Display tokens are not keys."""

    canonical_by_entity_id: dict[str, str] = Field(default_factory=dict)
    rejected_pairs: list[list[str]] = Field(default_factory=list)
    family_order: dict[str, list[str]] = Field(default_factory=dict)
    append_ids: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    job_id: str
    file_name: str
    document_kind: DocumentKind
    document_hash: str
    page_count: int
    text: str
    page_texts: list[str] = []  # Per-page text; empty for TEXT/DOCX documents
    page_spans: list[dict] = []  # PDF overlay boxes, computed during analysis
    page_previews: list[dict] = []  # [{page, image}] data URLs for the first rendered pages
    entities: list[EntityCandidate]
    detectors_executed: list[str]
    warnings: list[str] = []
    profile: PrivacyProfile
    detection_mode: DetectionMode = DetectionMode.LOCAL_CONTEXT
    routing: RoutingMetadata | None = None
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETE
    ai_status: AIRunStatus = AIRunStatus.DISABLED
    ai_error_code: str | None = None
    ai_error_message: str | None = None
    local_ner_status: LocalNERStatus = LocalNERStatus.NOT_REQUESTED
    local_ner_language: str | None = None
    local_ner_provider: str | None = None
    local_ner_candidate_count: int | None = None
    local_ner_error_code: str | None = None
    local_ner_error_message: str | None = None
    requested_document_language: str | None = None
    resolved_document_language: str | None = None
    possible_matches: list[PossibleMatch] = Field(default_factory=list)
    resolution_state: ResolutionState | None = None


class RedactionDecision(BaseModel):
    entity_id: str
    action: Literal["REDACT", "KEEP"]
    strategy: TransformationStrategy | None = None
    source: DecisionSource = DecisionSource.DEFAULT
    parameters: dict[str, Any] = Field(default_factory=dict)


class CategoryTransformDefault(BaseModel):
    category: EntityType
    strategy: TransformationStrategy
    parameters: dict[str, Any] = Field(default_factory=dict)


class UserDefinedTerm(BaseModel):
    value: str = Field(min_length=2, max_length=200)
    category: EntityType = EntityType.PERSON_NAME
    strategy: TransformationStrategy | None = None
    stable_key: str | None = None
    starts: list[int] | None = None


class CustomTermsRequest(BaseModel):
    terms: list[UserDefinedTerm]


class ManualRedaction(BaseModel):
    page: int = Field(ge=0)
    text: str = Field(min_length=1)
    replacement: str | None = None  # Custom replacement text; None → REDACT (black box)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, gt=0)
    rectangles: list[ManualRect] = Field(default_factory=list)
    fill: str | None = None
    text_color: str | None = None
    font: str | None = None
    font_size: float | None = None


class RedactionRequest(BaseModel):
    decisions: list[RedactionDecision]
    manual_redactions: list[ManualRedaction] = []
    category_defaults: list[CategoryTransformDefault] = []
    # Legacy global method; mapped to REDACT/PLACEHOLDER when strategies absent.
    method: Literal["MASK", "LABEL"] | None = None
    output_format: Literal["PDF", "DOCX", "TXT"] | None = None
    locale: Literal["tr", "en"] = "tr"
    initials_font_size: float | None = Field(default=None, ge=4, le=72)


class PreviewRequest(BaseModel):
    decisions: list[RedactionDecision]
    category_defaults: list[CategoryTransformDefault] = []
    manual_redactions: list[ManualRedaction] = []
    method: Literal["MASK", "LABEL"] | None = None
    locale: Literal["tr", "en"] = "tr"
    initials_font_size: float | None = Field(default=None, ge=4, le=72)


class PreviewOperation(BaseModel):
    entity_id: str | None = None
    category: str | None = None
    strategy: TransformationStrategy
    start: int
    end: int
    replacement: str
    export_path: Literal["secure_pdf", "text_rebuild"]
    ai_assisted: bool = False


class PreviewResponse(BaseModel):
    text: str
    operations: list[PreviewOperation]
    requires_text_rebuild: bool
    warnings: list[str] = []
    placeholder_tokens: dict[str, str] = Field(default_factory=dict)


class EntityMatchRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=2)


class ReclassifyRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=1)
    entity_type: EntityType


class ProfileUpdateRequest(BaseModel):
    profile: PrivacyProfile


class ValidationStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAILED = "FAILED"


class ValidationResult(BaseModel):
    status: ValidationStatus
    selected_count: int
    remaining_selected_values: int
    messages: list[str]
    strategy_results: list[dict[str, Any]] = Field(default_factory=list)
    operation_messages: list[str] = Field(default_factory=list)
    residual_messages: list[str] = Field(default_factory=list)
    verified_count: int = 0
    warning_count: int = 0
    failed_count: int = 0


class StrategyAuditEntry(BaseModel):
    category: str
    role: str | None = None
    occurrences: int
    strategy: TransformationStrategy
    decision_source: DecisionSource
    validation: ValidationStatus
    ai_assisted: bool = False
    user_reviewed: bool | None = None
    user_decision: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    validation_reasons: list[str] = Field(default_factory=list)
    mapping_coarse: bool = False


class AuditReport(BaseModel):
    audit_version: str = "3"
    application_version: str
    policy_version: str
    document_hash: str
    document_kind: DocumentKind
    output_format: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    privacy_profile: PrivacyProfile
    detection_mode: DetectionMode = DetectionMode.LOCAL_CONTEXT
    detectors_executed: list[str]
    detected_category_counts: dict[str, int]
    redacted_category_counts: dict[str, int]
    kept_count: int
    manual_redaction_count: int
    redaction_method: str
    strategy_counts: dict[str, int] = Field(default_factory=dict)
    export_path: Literal["secure_pdf", "text_rebuild", "clean_layout"] = "secure_pdf"
    output_mode: Literal["original_layout", "clean_layout"] = "original_layout"
    source_text_extraction_method: Literal["native", "ocr"] | None = None
    content_integrity_validation: Literal["pass", "fail"] | None = None
    privacy_validation: Literal["pass", "fail"] | None = None
    transformations: list[StrategyAuditEntry] = Field(default_factory=list)
    validation: ValidationResult
    analysis_status: AnalysisStatus | None = None
    ai_status: AIRunStatus | None = None
    analysis_warnings: list[str] = Field(default_factory=list)
