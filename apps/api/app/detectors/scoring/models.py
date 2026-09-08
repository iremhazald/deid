"""Internal deterministic evidence model. Score is not a probability."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.models import EntityCandidate, EntityType, VerificationLevel


class CandidateClass(StrEnum):
    STRICT = "STRICT"
    STRUCTURED = "STRUCTURED"
    COMPOSITE = "COMPOSITE"


class HardValidation(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ScoringDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    IGNORE = "IGNORE"


class EvidenceSource(StrEnum):
    VALIDATOR = "validator"
    STRUCTURE = "structure"
    CONTEXT = "context"
    LEXICON = "lexicon"
    NEGATIVE = "negative"
    DETECTOR = "detector"
    LOCAL = "local"
    USER = "user"
    DERIVED = "derived"


@dataclass(frozen=True)
class Evidence:
    """One deterministic signal. ``weight`` is an evidence weight, not confidence."""

    code: str
    weight: int
    source: str
    hard_reject: bool = False


@dataclass
class ScoredCandidate:
    entity: EntityCandidate
    candidate_class: CandidateClass
    hard_validation: HardValidation
    evidence: list[Evidence] = field(default_factory=list)
    negative_evidence: list[Evidence] = field(default_factory=list)
    evidence_score: int = 0
    decision: ScoringDecision = ScoringDecision.IGNORE
    conflict_reason: str | None = None
    parent_candidate_id: str | None = None

    @property
    def type(self) -> EntityType:
        return self.entity.type

    @property
    def start(self) -> int:
        return self.entity.start

    @property
    def end(self) -> int:
        return self.entity.end

    @property
    def page(self) -> int:
        return self.entity.page

    @property
    def detector(self) -> str:
        return self.entity.detector


def verification_for(decision: ScoringDecision, hard: HardValidation) -> VerificationLevel:
    if decision == ScoringDecision.ACCEPT and hard == HardValidation.VALID:
        return VerificationLevel.VALIDATED
    return VerificationLevel.REVIEW_RECOMMENDED
