"""Fail-closed inspection of a DOCX package before python-docx opens it.

The check reads ZIP headers and one small content-types member in memory.
It does not extract the archive, follow external relationships, or execute
macros, OLE objects, or any other embedded payload.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from app.domain.models import DocumentKind

MAX_ZIP_ENTRIES = 1024
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
RATIO_FLOOR_BYTES = 1024 * 1024
CONTENT_TYPES_READ_LIMIT = 1_000_000

_EXECUTABLE_SUFFIXES = {
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".msi",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
}
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


class UploadRejected(ValueError):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


def classify_upload(filename: str | None, content: bytes) -> DocumentKind:
    """Authoritative source type. Workspace mode is chosen separately.

    A PDF renamed .docx or .udf is rejected. A UYAP UDF package is recognized
    by content even when the extension is .pdf or .docx.
    """
    if not filename or not str(filename).strip():
        raise UploadRejected(400, "FILE_NAME_REQUIRED")
    extension = Path(str(filename)).suffix.lower()
    if extension == ".pdf":
        if content.startswith(b"%PDF-"):
            return DocumentKind.PDF
        if _accepted_udf(content):
            return DocumentKind.UDF
        raise UploadRejected(400, "INVALID_PDF")
    if extension == ".docx":
        if content.startswith(b"%PDF-"):
            raise UploadRejected(400, "INVALID_DOCX")
        try:
            preflight_docx_bytes(content)
        except UploadRejected as exc:
            if exc.code in {"INVALID_DOCX", "DOCX_CORRUPT"} and _accepted_udf(content):
                return DocumentKind.UDF
            raise
        return DocumentKind.DOCX
    if extension == ".udf":
        if content.startswith(b"%PDF-"):
            raise UploadRejected(400, "INVALID_UDF")
        from app.services.udf_package import preflight_udf_bytes

        preflight_udf_bytes(content)
        return DocumentKind.UDF
    raise UploadRejected(415, "DOCUMENT_FORMAT_UNSUPPORTED")


def _accepted_udf(content: bytes) -> bool:
    from app.services.udf_package import preflight_udf_bytes

    try:
        preflight_udf_bytes(content)
    except UploadRejected as exc:
        if exc.code in {"INVALID_UDF", "UDF_CORRUPT", "UDF_FORMAT_UNSUPPORTED"}:
            return False
        raise
    return True


def preflight_docx_path(path: Path, **limits: int) -> None:
    with path.open("rb") as handle:
        head = handle.read(8)
    _reject_obvious_non_docx(head)
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadRejected(400, "DOCX_CORRUPT") from exc
    with archive:
        _inspect_archive(archive, **limits)


def preflight_docx_bytes(content: bytes, **limits: int) -> None:
    _reject_obvious_non_docx(content[:8])
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadRejected(400, "DOCX_CORRUPT") from exc
    with archive:
        _inspect_archive(archive, **limits)


def _reject_obvious_non_docx(head: bytes) -> None:
    if head.startswith(b"%PDF-"):
        raise UploadRejected(400, "INVALID_DOCX")
    if not head.startswith(b"PK"):
        raise UploadRejected(400, "INVALID_DOCX")


def _inspect_archive(
    archive: zipfile.ZipFile,
    *,
    max_entries: int = MAX_ZIP_ENTRIES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
    max_ratio: int = MAX_COMPRESSION_RATIO,
    ratio_floor: int = RATIO_FLOOR_BYTES,
) -> None:
    members = [info for info in archive.infolist() if not info.is_dir()]
    if len(archive.infolist()) > max_entries:
        raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")

    total_uncompressed = 0
    for info in members:
        name = info.filename
        if _unsafe_member_name(name) or _executable_member(name):
            raise UploadRejected(400, "DOCX_UNSAFE_ARCHIVE")
        if _macro_member(name):
            raise UploadRejected(400, "MACRO_DOCUMENT_UNSUPPORTED")
        if info.file_size < 0 or info.file_size > max_uncompressed:
            raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")
        total_uncompressed += info.file_size
        if total_uncompressed > max_uncompressed:
            raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")
        compressed = max(info.compress_size, 1)
        if info.file_size >= ratio_floor and info.file_size / compressed > max_ratio:
            raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")

    document = _find_member(archive, "word/document.xml")
    content_types = _find_member(archive, "[Content_Types].xml")
    if document is None or content_types is None or document.file_size <= 0:
        raise UploadRejected(400, "INVALID_DOCX")

    payload = _read_capped(archive, content_types, CONTENT_TYPES_READ_LIMIT)
    lowered = payload.lower()
    if b"macroenabled" in lowered or b"vbaproject" in lowered:
        raise UploadRejected(400, "MACRO_DOCUMENT_UNSUPPORTED")
    if b"wordprocessingml.document.main+xml" not in lowered:
        raise UploadRejected(400, "INVALID_DOCX")


def _read_capped(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if info.file_size > limit:
        raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")
    with archive.open(info, "r") as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise UploadRejected(413, "DOCX_LIMIT_EXCEEDED")
    return payload


def _find_member(archive: zipfile.ZipFile, target: str) -> zipfile.ZipInfo | None:
    wanted = target.lower()
    for info in archive.infolist():
        if info.filename.replace("\\", "/").lower() == wanted:
            return info
    return None


def _unsafe_member_name(name: str) -> bool:
    if "\x00" in name:
        return True
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_LETTER.match(name) or _DRIVE_LETTER.match(normalized):
        return True
    return any(part == ".." for part in normalized.split("/"))


def _executable_member(name: str) -> bool:
    return Path(name.replace("\\", "/")).suffix.lower() in _EXECUTABLE_SUFFIXES


def _macro_member(name: str) -> bool:
    lowered = name.replace("\\", "/").lower()
    return lowered.endswith("vbaproject.bin") or lowered.endswith(".docm")
