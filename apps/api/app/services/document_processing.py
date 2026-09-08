from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pymupdf
from docx import Document

from app.detectors.registry import PageText
from app.services.jobs import SpanBox

_ocr_engine: Any | None = None


def _get_ocr_engine() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def extract_pdf_with_ocr(
    document: pymupdf.Document,
) -> tuple[list[PageText], str, list[SpanBox], bool]:
    pages: list[PageText] = []
    chunks: list[str] = []
    span_boxes: list[SpanBox] = []
    document_offset = 0
    ocr_used = False

    for page_number in range(document.page_count):
        page = document[page_number]
        native_text = str(page.get_text("text"))
        if native_text.strip():
            page_text = native_text
        else:
            ocr_used = True
            zoom = 2.0
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            result = _get_ocr_engine()(pixmap.tobytes("png"))
            texts = list(result.txts) if result.txts is not None else []
            boxes = list(result.boxes) if result.boxes is not None else []
            line_chunks: list[str] = []
            local_offset = 0
            for text, box in zip(texts, boxes, strict=False):
                clean = str(text).strip()
                if not clean:
                    continue
                line_chunks.append(clean)
                points = list(box)
                x_values = [float(point[0]) / zoom for point in points]
                y_values = [float(point[1]) / zoom for point in points]
                span_boxes.append(
                    SpanBox(
                        page=page_number,
                        start=document_offset + local_offset,
                        end=document_offset + local_offset + len(clean),
                        rectangle=(
                            min(x_values),
                            min(y_values),
                            max(x_values),
                            max(y_values),
                        ),
                    )
                )
                local_offset += len(clean) + 1
            page_text = "\n".join(line_chunks)
            if page_text:
                page_text += "\n"

        pages.append(PageText(page_number, page_text, document_offset))
        chunks.append(page_text)
        document_offset += len(page_text)

    return pages, "".join(chunks), span_boxes, ocr_used


def _table_text(table: Any) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        lines.append("\t".join(cell.text for cell in row.cells))
    return lines


def extract_docx(path: Path) -> str:
    try:
        document = Document(str(path))
    except Exception as exc:
        raise ValueError("DOCX_CORRUPT") from exc

    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        lines.extend(_table_text(table))
    for section in document.sections:
        lines.extend(paragraph.text for paragraph in section.header.paragraphs)
        lines.extend(paragraph.text for paragraph in section.footer.paragraphs)
    return "\n".join(line for line in lines if line.strip())


def redact_text_content(
    text: str,
    spans: list[tuple[int, int, str]],
    manual_values: list[str],
    method: str,
) -> tuple[str, list[str]]:
    selected_values: list[str] = []
    replacements: list[tuple[int, int, str]] = []
    counters: dict[str, int] = {}

    for start, end, entity_type in spans:
        original = text[start:end]
        selected_values.append(original)
        counters[entity_type] = counters.get(entity_type, 0) + 1
        replacement = (
            f"[{entity_type}_{counters[entity_type]}]"
            if method == "LABEL"
            else "█" * max(1, len(original))
        )
        replacements.append((start, end, replacement))

    for value in manual_values:
        cursor = 0
        found_any = False
        while True:
            start = text.find(value, cursor)
            if start < 0:
                break
            found_any = True
            selected_values.append(value)
            replacement = (
                "[MANUAL_REDACTION]"
                if method == "LABEL"
                else "█" * max(1, len(value))
            )
            replacements.append((start, start + len(value), replacement))
            cursor = start + len(value)
        if not found_any:
            raise ValueError("SPAN_MAPPING_FAILED")

    # Remove overlapping operations conservatively, then edit back-to-front so
    # offsets remain stable.
    accepted: list[tuple[int, int, str]] = []
    for operation in sorted(replacements, key=lambda item: (item[0], -item[1])):
        if any(operation[0] < other[1] and operation[1] > other[0] for other in accepted):
            continue
        accepted.append(operation)
    output = text
    for start, end, replacement in sorted(accepted, reverse=True):
        output = output[:start] + replacement + output[end:]
    return output, selected_values


def write_text_output(text: str, path: Path, output_format: str) -> None:
    if output_format == "TXT":
        path.write_text(text, encoding="utf-8")
        return
    if output_format == "DOCX":
        document = Document()
        for line in text.splitlines() or [""]:
            document.add_paragraph(line)
        document.core_properties.title = "Redacted legal document"
        document.core_properties.author = ""
        document.core_properties.subject = ""
        document.core_properties.comments = ""
        document.save(str(path))
        return
    if output_format != "PDF":
        raise ValueError("OUTPUT_FORMAT_INVALID")

    document = pymupdf.open()
    lines = text.splitlines() or [""]
    for start in range(0, len(lines), 45):
        page = document.new_page()
        body = html.escape("\n".join(lines[start : start + 45]))
        page.insert_htmlbox(
            pymupdf.Rect(50, 50, page.rect.width - 50, page.rect.height - 50),
            f"<pre style='font-family:sans-serif;font-size:10pt'>{body}</pre>",
        )
    document.save(path, garbage=4, deflate=True, clean=True)
    document.close()


def extract_generated_output(path: Path, output_format: str) -> str:
    if output_format == "TXT":
        return path.read_text(encoding="utf-8")
    if output_format == "DOCX":
        return extract_docx(path)
    document = pymupdf.open(path)
    try:
        return "".join(
            str(document[index].get_text("text"))
            for index in range(document.page_count)
        )
    finally:
        document.close()
