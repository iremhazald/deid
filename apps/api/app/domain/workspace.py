"""Source type and workspace mode. These are independent of each other."""

from __future__ import annotations

from app.domain.models import DocumentKind, SourceDocumentType, WorkspaceMode


def parse_workspace_mode(raw: str | None) -> WorkspaceMode:
    """Omitted or blank means the V1 PDF workspace."""
    if raw is None:
        return WorkspaceMode.DOCUMENT
    value = raw.strip().upper()
    if not value:
        return WorkspaceMode.DOCUMENT
    try:
        return WorkspaceMode(value)
    except ValueError as exc:
        raise ValueError("WORKSPACE_MODE_INVALID") from exc


def workspace_mode_for_upload(kind: DocumentKind, raw: str | None) -> WorkspaceMode:
    """PDF keeps the caller's choice. DOCX and UYAP UDF always use text."""
    if kind in {DocumentKind.DOCX, DocumentKind.UDF}:
        return WorkspaceMode.TEXT
    if kind != DocumentKind.PDF:
        return WorkspaceMode.DOCUMENT
    return parse_workspace_mode(raw)


def source_document_type_for_kind(kind: DocumentKind) -> SourceDocumentType | None:
    if kind == DocumentKind.PDF:
        return SourceDocumentType.PDF
    if kind == DocumentKind.DOCX:
        return SourceDocumentType.DOCX
    if kind == DocumentKind.UDF:
        return SourceDocumentType.UDF
    return None
