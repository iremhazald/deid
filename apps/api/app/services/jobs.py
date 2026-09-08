from __future__ import annotations

import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.models import (
    AnalysisResponse,
    AuditReport,
    DocumentKind,
    ResolutionState,
    UserDefinedTerm,
)


@dataclass(frozen=True)
class SpanBox:
    page: int
    start: int
    end: int
    rectangle: tuple[float, float, float, float]


@dataclass
class Job:
    id: str
    directory: Path
    source_path: Path
    document_kind: DocumentKind
    created_at: float
    last_accessed: float = 0.0
    analysis: AnalysisResponse | None = None
    output_path: Path | None = None
    audit: AuditReport | None = None
    page_texts: list[str] = field(default_factory=list)
    span_boxes: list[SpanBox] = field(default_factory=list)
    page_spans: list[dict] = field(default_factory=list)
    page_images: dict[str, bytes] = field(default_factory=dict)
    output_name: str | None = None
    output_media_type: str | None = None
    saved_output_path: Path | None = None
    saved_audit_path: Path | None = None
    custom_terms: list[UserDefinedTerm] = field(default_factory=list)
    scan_types: list[str] | None = None
    locale: str = "tr"
    requested_document_language: str | None = None
    resolution_state: ResolutionState = field(default_factory=ResolutionState)
    page_render_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _pdf: Any = field(default=None, repr=False)

    def close_resources(self) -> None:
        document = self._pdf
        self._pdf = None
        closer = getattr(document, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass


class JobStore:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._jobs: dict[str, Job] = {}

    def cleanup(self) -> None:
        now = time.time()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if now - (job.last_accessed or job.created_at) > self.ttl_seconds
        ]
        for job_id in expired:
            self.delete(job_id)

    def create(
        self,
        file_name: str,
        content: bytes,
        document_kind: DocumentKind = DocumentKind.PDF,
    ) -> Job:
        self.cleanup()
        job_id = str(uuid4())
        directory = Path(tempfile.mkdtemp(prefix="legal-redaction-"))
        safe_name = Path(file_name).name
        source = directory / safe_name
        source.write_bytes(content)
        job = Job(job_id, directory, source, document_kind, time.time(), last_accessed=time.time())
        self._jobs[job_id] = job
        return job

    def create_text(self, text: str) -> Job:
        return self.create(
            "input.txt", text.encode("utf-8"), DocumentKind.TEXT
        )

    def get(self, job_id: str) -> Job:
        self.cleanup()
        if job_id not in self._jobs:
            raise KeyError(job_id)
        job = self._jobs[job_id]
        job.last_accessed = time.time()
        return job

    def delete(self, job_id: str) -> None:
        job = self._jobs.pop(job_id, None)
        if job:
            job.close_resources()
            shutil.rmtree(job.directory, ignore_errors=True)
