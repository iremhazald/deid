"""The new DOCX download is a fresh document, not the original package."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

_EMAIL = "export-meta@example.com"
_ORIGINAL_AUTHOR = "ORIGINAL-AUTHOR-META"
_ORIGINAL_EDITOR = "ORIGINAL-EDITOR-META"
_ORIGINAL_COMMENT = "ORIGINAL-COMMENT-META"
_ORIGINAL_CUSTOM = "ORIGINAL-CUSTOM-META"


def _write_member(path: Path, name: str, payload: bytes) -> None:
    original = path.read_bytes()
    outgoing = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(outgoing, "w") as target:
        replaced = False
        for info in source.infolist():
            member = info.filename.replace("\\", "/")
            if member == name:
                target.writestr(info, payload)
                replaced = True
            else:
                target.writestr(info, source.read(info.filename))
        if not replaced:
            target.writestr(name, payload)
    path.write_bytes(outgoing.getvalue())


def _poisoned_docx(path: Path) -> bytes:
    document = Document()
    document.add_paragraph(f"Contact {_EMAIL} about the file.")
    document.core_properties.author = _ORIGINAL_AUTHOR
    document.core_properties.last_modified_by = _ORIGINAL_EDITOR
    document.core_properties.comments = _ORIGINAL_COMMENT
    document.core_properties.title = "Original Title"
    document.core_properties.subject = "Original Subject"
    document.save(path)
    with zipfile.ZipFile(path) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")
    if "</w:body>" not in document_xml:
        raise AssertionError("source document has no body")
    tracked = (
        "<w:p>"
        f'<w:ins w:id="1" w:author="{_ORIGINAL_EDITOR}" w:date="2026-01-01T00:00:00Z">'
        "<w:r><w:t>TRACKED-INSERT</w:t></w:r></w:ins>"
        f'<w:del w:id="2" w:author="{_ORIGINAL_EDITOR}" w:date="2026-01-01T00:00:00Z">'
        "<w:r><w:delText>TRACKED-DELETE</w:delText></w:r></w:del>"
        "</w:p></w:body>"
    )
    _write_member(path, "word/document.xml", document_xml.replace("</w:body>", tracked, 1).encode())
    _write_member(
        path,
        "word/comments.xml",
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:comment w:id="0" w:author="{_ORIGINAL_AUTHOR}" w:date="2026-01-01T00:00:00Z">'
            f"<w:p><w:r><w:t>{_ORIGINAL_COMMENT}</w:t></w:r></w:p></w:comment>"
            "</w:comments>"
        ).encode(),
    )
    _write_member(
        path,
        "docProps/custom.xml",
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="CourtSecret">'
            f"<vt:lpwstr>{_ORIGINAL_CUSTOM}</vt:lpwstr></property></Properties>"
        ).encode(),
    )
    return path.read_bytes()


def _xml_parts(data: bytes) -> tuple[list[str], bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        names = [name.replace("\\", "/") for name in package.namelist()]
        xml = b"".join(
            package.read(name)
            for name in package.namelist()
            if name.replace("\\", "/").endswith(".xml")
        )
    return names, xml


def test_new_docx_export_drops_original_metadata(tmp_path: Path) -> None:
    source = _poisoned_docx(tmp_path / "poison.docx")
    _names, source_xml = _xml_parts(source)
    for marker in (_ORIGINAL_AUTHOR, _ORIGINAL_EDITOR, _ORIGINAL_COMMENT, _ORIGINAL_CUSTOM):
        assert marker.encode() in source_xml
    assert b"<w:ins " in source_xml and b"<w:del " in source_xml

    from app.main import app

    with TestClient(app) as client:
        analyzed = client.post(
            "/api/documents/analyze",
            files={
                "file": (
                    "poison.docx",
                    source,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"document_language": "en", "mode": "RULES_ONLY", "workspace_mode": "DOCUMENT"},
        )
        assert analyzed.status_code == 200, analyzed.text
        body = analyzed.json()
        email = next(entity for entity in body["entities"] if entity["text"] == _EMAIL)
        redacted = client.post(
            f"/api/jobs/{body['job_id']}/redact",
            json={"decisions": [{"entity_id": email["id"], "action": "REDACT", "strategy": "REDACT"}]},
        )
        assert redacted.status_code == 200, redacted.text
        download = next(item for item in redacted.json()["downloads"] if item["format"] == "DOCX")
        exported = client.get(download["url"])
        assert exported.status_code == 200

    names, xml = _xml_parts(exported.content)
    for marker in (_ORIGINAL_AUTHOR, _ORIGINAL_EDITOR, _ORIGINAL_COMMENT, _ORIGINAL_CUSTOM):
        assert marker.encode() not in xml
    assert "word/comments.xml" not in names
    assert "docProps/custom.xml" not in names
    with zipfile.ZipFile(io.BytesIO(exported.content)) as package:
        document_xml = package.read("word/document.xml")
    assert b"<w:ins " not in document_xml and b"<w:ins>" not in document_xml
    assert b"<w:del " not in document_xml and b"<w:del>" not in document_xml
    assert b"w:comment" not in document_xml
