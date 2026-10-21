"""Local reader for UYAP Editor .udf packages.

Supported packages are ZIP archives whose document text is the direct
<template><content> value in content.xml. format_id 1.7 and 1.8 are the
versions identified from public UYAP samples. sign.sgn is signature material
and is never treated as text. Structural startOffset values are Unicode code
points; they are applied only when they are identical to UTF-16 indexes.
"""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.services.docx_preflight import UploadRejected

MAX_ZIP_ENTRIES = 64
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
RATIO_FLOOR_BYTES = 1024 * 1024
SUPPORTED_FORMAT_IDS = frozenset({"1.7", "1.8"})
_ALLOWED_MEMBERS = frozenset({"content.xml", "sign.sgn", "documentproperties.xml"})
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


@dataclass(frozen=True)
class UdfText:
    text: str
    warnings: tuple[str, ...]


def preflight_udf_bytes(content: bytes, **limits: int) -> None:
    if content.startswith(b"%PDF-") or not content.startswith(b"PK"):
        raise UploadRejected(400, "INVALID_UDF")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadRejected(400, "UDF_CORRUPT") from exc
    with archive:
        _inspect_archive(archive, **limits)


def preflight_udf_path(path: Path, **limits: int) -> None:
    with path.open("rb") as handle:
        head = handle.read(8)
    if head.startswith(b"%PDF-") or not head.startswith(b"PK"):
        raise UploadRejected(400, "INVALID_UDF")
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadRejected(400, "UDF_CORRUPT") from exc
    with archive:
        _inspect_archive(archive, **limits)


def extract_udf_text(path: Path, *, max_chars: int | None = None) -> UdfText:
    preflight_udf_path(path)
    with zipfile.ZipFile(path) as archive:
        names = _member_names(archive)
        payload = _read_content_xml(archive)
        warnings = _package_warnings(names)
    text, structured_warning = _text_from_content_xml(payload)
    if structured_warning and structured_warning not in warnings:
        warnings = (*warnings, structured_warning)
    limit = max_chars if max_chars is not None else get_settings().redaction_max_extracted_chars
    if len(text) > limit:
        raise UploadRejected(413, "UDF_TOO_LARGE")
    if not text.strip():
        raise UploadRejected(400, "INVALID_UDF")
    return UdfText(text, warnings)


def _inspect_archive(
    archive: zipfile.ZipFile,
    *,
    max_entries: int = MAX_ZIP_ENTRIES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
    max_ratio: int = MAX_COMPRESSION_RATIO,
    ratio_floor: int = RATIO_FLOOR_BYTES,
) -> None:
    if len(archive.infolist()) > max_entries:
        raise UploadRejected(413, "UDF_TOO_LARGE")
    names = _member_names(archive)
    if names.count("content.xml") > 1:
        raise UploadRejected(400, "UDF_CORRUPT")
    total = 0
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        if _unsafe_member_name(name) or _executable_member(name):
            raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
        if info.file_size < 0 or info.file_size > max_uncompressed:
            raise UploadRejected(413, "UDF_TOO_LARGE")
        total += info.file_size
        if total > max_uncompressed:
            raise UploadRejected(413, "UDF_TOO_LARGE")
        compressed = max(info.compress_size, 1)
        if info.file_size >= ratio_floor and info.file_size / compressed > max_ratio:
            raise UploadRejected(413, "UDF_TOO_LARGE")
    if "content.xml" not in names:
        raise UploadRejected(400, "INVALID_UDF")
    if any(name not in _ALLOWED_MEMBERS for name in names):
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    _text_from_content_xml(_read_content_xml(archive))


def _member_names(archive: zipfile.ZipFile) -> list[str]:
    return [
        info.filename.replace("\\", "/")
        for info in archive.infolist()
        if not info.is_dir()
    ]


def _read_content_xml(archive: zipfile.ZipFile) -> bytes:
    info = archive.getinfo("content.xml")
    if info.file_size > MAX_XML_BYTES:
        raise UploadRejected(413, "UDF_TOO_LARGE")
    with archive.open(info, "r") as handle:
        payload = handle.read(MAX_XML_BYTES + 1)
    if len(payload) > MAX_XML_BYTES:
        raise UploadRejected(413, "UDF_TOO_LARGE")
    return payload


def _package_warnings(names: list[str]) -> tuple[str, ...]:
    if any(name != "content.xml" for name in names):
        return ("UDF_UNSUPPORTED_CONTENT",)
    return ()


def _text_from_content_xml(payload: bytes) -> tuple[str, str | None]:
    if b"<!doctype" in payload.lower() or b"<!entity" in payload.lower():
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    if not _declares_utf8(payload):
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    try:
        xml_text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise UploadRejected(400, "UDF_CORRUPT") from exc
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise UploadRejected(400, "UDF_CORRUPT") from exc
    if _local(root.tag) != "template":
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    if root.attrib.get("format_id", "").strip() not in SUPPORTED_FORMAT_IDS:
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    contents = [child for child in list(root) if _local(child.tag) == "content"]
    if len(contents) != 1 or list(contents[0]):
        raise UploadRejected(400, "UDF_FORMAT_UNSUPPORTED")
    source = contents[0].text or ""
    warning = "UDF_UNSUPPORTED_CONTENT" if "\ufffc" in source else None
    plain = _normalize_plain(source)
    elements = next((child for child in list(root) if _local(child.tag) == "elements"), None)
    if elements is not None and any(_local(node.tag) == "image" for node in elements.iter()):
        warning = "UDF_UNSUPPORTED_CONTENT"
    if elements is None or not _offsets_are_unambiguous(source):
        return plain, warning
    try:
        structured = _render_elements(elements, source)
    except ValueError:
        return plain, warning
    if not structured.strip():
        return plain, warning
    return structured, warning


def _declares_utf8(payload: bytes) -> bool:
    head = payload.lstrip()[:240].lower()
    if not head.startswith(b"<?xml") or b"encoding" not in head:
        return True
    return b'encoding="utf-8"' in head or b"encoding='utf-8'" in head


def _offsets_are_unambiguous(text: str) -> bool:
    """UTF-16 code units and Unicode code points match for BMP text."""
    return all(ord(char) <= 0xFFFF for char in text)


def _normalize_plain(text: str) -> str:
    return text.replace("\u200b", "").replace("\ufffc", "").replace("\r\n", "\n").replace("\r", "")


def _render_elements(elements: ET.Element, source: str) -> str:
    blocks = _blocks(elements, source)
    return "\n".join(blocks)


def _blocks(parent: ET.Element, source: str) -> list[str]:
    blocks: list[str] = []
    for child in list(parent):
        name = _local(child.tag)
        if name == "paragraph":
            line = _paragraph_text(child, source)
            if line:
                blocks.append(line)
        elif name == "table":
            rows = _table_rows(child, source)
            if rows:
                blocks.append("\n".join(rows))
    return blocks


def _table_rows(table: ET.Element, source: str) -> list[str]:
    rows: list[str] = []
    for row in list(table):
        if _local(row.tag) != "row":
            continue
        cells: list[str] = []
        for cell in list(row):
            if _local(cell.tag) != "cell":
                continue
            cells.append(" ".join(_blocks(cell, source)))
        if any(cell.strip() for cell in cells):
            rows.append("\t".join(cells))
    return rows


def _paragraph_text(paragraph: ET.Element, source: str) -> str:
    parts: list[str] = []
    for child in list(paragraph):
        name = _local(child.tag)
        if name == "content":
            parts.append(_slice(source, child))
        elif name == "tab":
            parts.append("\t")
    return "".join(parts).replace("\r", "").rstrip("\n")


def _slice(source: str, element: ET.Element) -> str:
    start = _attr_int(element, "startOffset", _attr_int(element, "offset"))
    length = _attr_int(element, "length")
    if start < 0 or length < 0 or start + length > len(source):
        raise ValueError("offset")
    return source[start : start + length].replace("\u200b", "").replace("\ufffc", "")


def _attr_int(element: ET.Element, name: str, fallback: int = 0) -> int:
    raw = element.attrib.get(name)
    if raw in (None, ""):
        return fallback
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("offset") from exc


def _local(tag: str) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _unsafe_member_name(name: str) -> bool:
    if "\x00" in name:
        return True
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_LETTER.match(name) or _DRIVE_LETTER.match(normalized):
        return True
    return any(part == ".." for part in normalized.split("/"))


def _executable_member(name: str) -> bool:
    return Path(name.replace("\\", "/")).suffix.lower() in _EXECUTABLE_SUFFIXES
